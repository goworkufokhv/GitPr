from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "documents"
MODEL_NAME = "all-MiniLM-L6-v2" 

@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(MODEL_NAME)


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

    query_embedding = get_embedding_model().encode(query).tolist()
    query_options = {
        "query_embeddings": [query_embedding],
        "n_results": n_results
    }

    if document_id is not None:
        query_options["where"] = {"document_id": document_id}

    results = get_collection().query(**query_options)
    searched_documents = []

    for text, metadata in zip(
        results["documents"][0],
        results["metadatas"][0]
    ):
        searched_documents.append({
            "text": text,
            "file_name": metadata["file_name"],
            "page": metadata["page"],
            "chunk": metadata["chunk"],
            "document_id": metadata["document_id"]
        })

    return searched_documents
