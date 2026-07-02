import os
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


PDF_PATH = "C:\\단국대학교\\2학년\\1학기\\오픈소스SW기초 3분반\\기말고사\\09-Kubernetes-1.pdf"
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "pdf_documents"


def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if text:
            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


def split_text(text, chunk_size=500, overlap=100):
    chunks = []

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk)

        start = end - overlap

    return chunks


def save_pdf_to_chroma(pdf_path):

    pages = extract_text_from_pdf(pdf_path)

    print(f"추출된 페이지 수: {len(pages)}")

    if not pages:
        print("PDF에서 텍스트를 추출하지 못했습니다.")
        print("스캔 PDF이거나 이미지 기반 PDF일 가능성이 있습니다.")
        return
    
    if not os.path.exists(pdf_path):
        print(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        return

    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    #pages = extract_text_from_pdf(pdf_path)

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for page in pages:
        page_number = page["page"]
        text = page["text"]

        chunks = split_text(text)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{os.path.basename(pdf_path)}_p{page_number}_c{idx}"

            ids.append(chunk_id)
            documents.append(chunk)
            embeddings.append(model.encode(chunk).tolist())
            metadatas.append({
                "file_name": os.path.basename(pdf_path),
                "page": page_number,
                "chunk": idx
            })

    if not documents:
        print("저장할 chunk가 없습니다.")
        return
    
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    print(f"저장 완료: {len(documents)}개 chunk")


def search_chroma(query, n_results=1):
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results #정의되지 않았다는데 어떻게 수정해야 하지?
    )

    print("\n검색 결과")

    searched_docs=[]
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        searched_docs.append({
            "text":doc,
            #meta : 딕셔너리 전체를 저장하는 변수
            "file_name": meta["file_name"],#딕셔너리에서 "file_name"이라는 key의 value를 가져오는 코드
            "page": meta["page"],
            "chunk": meta["chunk"]
        })

    return searched_docs


if __name__ == "__main__":
    save_pdf_to_chroma(PDF_PATH)

    query = "이 문서의 핵심 내용은 뭐야?"
    search_chroma(query)