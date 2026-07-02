import chromadb
from sentence_transformers import SentenceTransformer

client=chromadb.PersistentClient(
    path="chroma_db"
)

collection=client.get_or_create_collection(
    name="documents"
)

model=SentenceTransformer(
    "all-MiniLM-L6-v2"
)

text = """
데이터베이스 관리 시스템(DBMS)은
데이터를 효율적으로 관리하는 소프트웨어이다.
"""

embedding=model.encode(text)

collection.add(
    documents=[text],
    embeddings=[embedding.tolist()],
    ids=["doc1"]
)

query="DBMS가 뭐야?"

query_embedding=model.encode(query)

results=collection.query(
    query_embeddings=[
        query_embedding.tolist()
    ],
    n_results=1
)

print(results["documents"])