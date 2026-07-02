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