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

    # overlap 적용 여부 확인용 임시 로그
    if overlap > 0 and len(chunks) >= 2:
        print("\n" + "=" * 60)
        print("[OVERLAP DEBUG]")
        print(f"chunk_size: {chunk_size}")
        print(f"overlap: {overlap}")
        print(f"step: {step}")
        print(f"생성된 chunk 수: {len(chunks)}")

        for index in range(len(chunks) - 1):
            current_end = chunks[index][-overlap:]
            next_start = chunks[index + 1][:overlap]

            print("-" * 60)
            print(f"chunk {index} → chunk {index + 1}")
            print(f"현재 chunk 마지막 {overlap}자:")
            print(repr(current_end))
            print(f"다음 chunk 처음 {overlap}자:")
            print(repr(next_start))
            print(f"완전히 일치하는지: {current_end == next_start}")

        print("=" * 60 + "\n")

    return chunks
