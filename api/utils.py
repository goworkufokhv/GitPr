from pypdf import PdfReader

def extract_text_from_pdf(file_path):
    reader=PdfReader(file_path)
    pages_text=[]

    for page_number, page in enumerate(reader.pages, start=1):
        text=page.extract_text()

        if text:
            pages_text.append({
                "page": page_number,
                "text":text
            })

    return pages_text


def split_text(text, chunk_size=700, overlap=150):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to 0 and less than chunk_size.")

    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size].strip()

        if chunk:
            chunks.append(chunk)

    return chunks
