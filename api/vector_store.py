from functools import lru_cache
from numbers import Real
import re

import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "documents"
MODEL_NAME = "all-MiniLM-L6-v2" 
SEARCH_CANDIDATE_K = 8
FINAL_CONTEXT_K = 5
MAX_DISTANCE = 1.25
MIN_CHUNK_TEXT_LENGTH = 50
MIN_CHUNK_WORD_COUNT = 5

SQL_KEYWORDS = (
    "CREATE",
    "ALTER",
    "DROP",
    "INSERT",
    "UPDATE",
    "DELETE",
    "SELECT",
    "COMMIT",
    "ROLLBACK",
    "GRANT",
    "REVOKE",
)
SQL_KEYWORD_PATTERN = "|".join(SQL_KEYWORDS)

client = chromadb.PersistentClient(path=CHROMA_PATH)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)

@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(MODEL_NAME)


def _has_sql_statement(text):
    sql_patterns = (
        r"CREATE\s+(?:TABLE|DATABASE|VIEW|INDEX|SCHEMA|SEQUENCE|USER)\b",
        r"ALTER\s+(?:TABLE|DATABASE|VIEW|USER)\b",
        r"DROP\s+(?:TABLE|DATABASE|VIEW|INDEX|SCHEMA|SEQUENCE|USER)\b",
        r"INSERT\s+INTO\b",
        r"UPDATE\s+\S+\s+SET\b",
        r"DELETE\s+FROM\b",
        r"SELECT\s+.+\s+FROM\b",
        r"(?:GRANT|REVOKE)\s+.+\s+(?:TO|FROM)\b",
        r"(?:COMMIT|ROLLBACK)\s*;",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in sql_patterns)


def _has_explanation(text):
    return bool(re.search(
        rf"(?:{SQL_KEYWORD_PATTERN})(?:는|은|이|가|란|이란)",
        text,
        re.IGNORECASE,
    ))


def _is_table_of_contents(text):
    if "목차" not in text:
        return False

    keyword_count = len(re.findall(
        rf"(?<![A-Za-z])(?:{SQL_KEYWORD_PATTERN})(?![A-Za-z])",
        text,
        re.IGNORECASE,
    ))
    return (
        keyword_count >= 2
        and not _has_explanation(text)
        and not _has_sql_statement(text)
    )


def _is_low_information_chunk(text):
    normalized_text = " ".join((text or "").split())
    body_text = re.sub(r"^\d+\s+", "", normalized_text).strip()

    if not body_text:
        return True

    if _is_table_of_contents(body_text):
        return True

    if _has_sql_statement(body_text) or _has_explanation(body_text):
        return False

    if not any(character.isalpha() for character in body_text):
        return True

    return (
        len(body_text) < MIN_CHUNK_TEXT_LENGTH
        or len(body_text.split()) < MIN_CHUNK_WORD_COUNT
    )


def save_chunks_to_chroma(document_id, file_name, chunks):
    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        text = chunk["text"].strip()

        if not text:
            continue

        page_number = chunk["page"]
        chunk_number = chunk["chunk"]

        ids.append(f"document_{document_id}_page_{page_number}_chunk_{chunk_number}")
        documents.append(text)
        metadatas.append({
            "document_id": document_id,
            "file_name": file_name,
            "page": page_number,
            "chunk": chunk_number
        })

    if not documents:
        return 0

    embeddings = get_embedding_model().encode(documents).tolist()

    get_collection().upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(documents)


def search_chroma(query, n_results=8, document_id=None):
    if not query or not query.strip():
        return []

    query_options = {
        "query_texts": [query],
        "n_results": SEARCH_CANDIDATE_K,
        "include": [
            "documents",
            "metadatas",
            "distances"
        ]
    }

    if document_id is not None:
        query_options["where"] = {"document_id": int(document_id)}

    results = collection.query(**query_options)
    searched_documents = []
    seen_metadata_keys = set()
    seen_text_keys = set()

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for text, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):
        normalized_text = " ".join((text or "").split())

        if _is_low_information_chunk(normalized_text):
            continue

        result_document_id = metadata.get("document_id")
        page = metadata.get("page")
        chunk = metadata.get("chunk")
        normalized_text_key = normalized_text.lower()

        metadata_key = (result_document_id, page, chunk)
        text_key = (result_document_id, page, normalized_text_key)

        if metadata_key in seen_metadata_keys or text_key in seen_text_keys:
            continue

        seen_metadata_keys.add(metadata_key)
        seen_text_keys.add(text_key)

        if isinstance(distance, Real) and distance > MAX_DISTANCE:
            continue

        searched_documents.append({
            "text": text,
            "file_name": metadata.get("file_name"),
            "page": page,
            "chunk": chunk,
            "document_id": result_document_id,
            "distance": float(distance) if isinstance(distance, Real) else distance,
        })

        if len(searched_documents) == FINAL_CONTEXT_K:
            break

    return searched_documents
