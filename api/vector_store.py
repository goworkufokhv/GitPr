from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "documents"
MODEL_NAME = "all-MiniLM-L6-v2" 

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

    results = collection.query(
    query_texts=[query],
    n_results=n_results,
    where={"document_id": int(document_id)} if document_id else None,
    include=[
        "documents",
        "metadatas",
        "distances"
    ]
)
    searched_documents = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for text, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):
        searched_documents.append({
            "text": text,
            "file_name": metadata.get("file_name"),
            "page": metadata.get("page"),
            "chunk": metadata.get("chunk"),
            "document_id": metadata.get("document_id"),
            "distance": float(distance),
        })

    return searched_documents
