from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema

from .models import Document
from .serializers import (
    ArticleAnalyzeRequestSerializer,
    ChatRequestSerializer,
    SummaryRequestSerializer,
)
from .article_utils import extract_article_text
from .utils import extract_text_from_pdf, split_text
from .vector_store import save_chunks_to_chroma
from .rag import (
    build_article_summary_prompt,
    build_prompt,
    build_summary_prompt,
    call_openai,
)
from .vector_store import save_chunks_to_chroma, search_chroma


class TestAPIView(APIView):
    def get(self, request):
        return Response({
            "message": "Django REST API 연결 성공",
            "status": "ok"
        })


class ChatAPIView(APIView):
    @extend_schema(
        request=ChatRequestSerializer,
        responses={200: None}
    )
    def post(self, request):
        #from .rag import build_prompt, call_openai
        #from .vector_store import search_chroma

        question = request.data.get("question")
        document_id = request.data.get("document_id")

        if not question:
            return Response({
                "error": "Question 값이 필요합니다."
            }, status=400)

        if document_id is None or document_id == "":
            return Response({
                "error": "질문할 문서를 선택해야 합니다."
            }, status=400)

        try:
            document_id = int(document_id)
        except (TypeError, ValueError):
            return Response({
                "error": "올바르지 않은 document_id입니다."
            }, status=400)

        try:
            searched_docs = search_chroma(
                question,
                document_id=document_id
            )

            if not searched_docs:
                return Response({
                    "answer": "선택한 문서에서 질문과 관련된 내용을 찾지 못했습니다.",
                    "sources": []
                }, status=200)
            print("\n" + "=" * 50)
            print("[DEBUG] ChromaDB 검색 결과")
            print(f"질문: {question}")
            print(f"검색된 chunk 수: {len(searched_docs)}")

            for idx, doc in enumerate(searched_docs, start=1):
                print("-" * 50)
                print(f"[{idx}] 파일: {doc.get('file_name')}")
                print(f"페이지: {doc.get('page')}")
                print(f"chunk: {doc.get('chunk')}")
                print(f"document_id: {doc.get('document_id')}")
                print(f"distance: {doc.get('distance')}")
                if "similarity" in doc:
                    print(f"similarity: {doc.get('similarity')}")
                print("내용 미리보기:")
                print(doc.get("text", "")[:500])

            print("=" * 50 + "\n")

            prompt = build_prompt(question, searched_docs)
            result = call_openai(prompt, parse_json=True)
            answer = result["answer"]
            used_sources = result.get("used_sources", [])

            valid_source_numbers = []
            seen_source_numbers = set()

            for source_number in used_sources:
                if not 1 <= source_number <= len(searched_docs):
                    continue
                if source_number in seen_source_numbers:
                    continue

                seen_source_numbers.add(source_number)
                valid_source_numbers.append(source_number)

            filtered_sources = [
                searched_docs[source_number - 1]
                for source_number in valid_source_numbers
            ]

            print("===== GPT USED SOURCES =====")
            print(f"used_sources: {valid_source_numbers}")
            print("\n===== FILTERED SOURCES =====")
            for source in filtered_sources:
                print(f"page: {source.get('page')}")

            return Response({
                "answer": answer,
                "sources": [{
                    "file_name": doc["file_name"],
                    "page": doc["page"],
                    "chunk": doc["chunk"],
                    "document_id": doc["document_id"],
                    "distance": doc["distance"]
                } for doc in filtered_sources]
            })
        except Exception as error:
            print(repr(error))
            return Response({
                "error": str(error)
            }, status=500)


class DocumentListAPIView(APIView):
    def get(self, request):
        documents = Document.objects.all().order_by("-uploaded_at")

        return Response({
            "documents": [
                {
                    "id": document.id,
                    "title": document.title,
                    "file_url": document.file.url,
                    "uploaded_at": document.uploaded_at
                }
                for document in documents
            ]
        })


class SummaryAPIView(APIView):
    @extend_schema(request=SummaryRequestSerializer, responses={200: None})
    def post(self, request):
        serializer = SummaryRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        document_id = serializer.validated_data["document_id"]
        summary_type = serializer.validated_data["summary_type"]

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({
                "error": "Document not found."
            }, status=404)

        pages_text = extract_text_from_pdf(document.file.path)

        if not pages_text or not any(page.get("text") for page in pages_text):
            return Response({
                "error": "No text found in document."
            }, status=400)

        prompt = build_summary_prompt(document.title, pages_text, summary_type)
        summary = call_openai(prompt)

        return Response({
            "document": {
                "id": document.id,
                "title": document.title
            },
            "summary_type": summary_type,
            "summary": summary
        })


class ArticleAnalyzeAPIView(APIView):
    @extend_schema(request=ArticleAnalyzeRequestSerializer, responses={200: None})
    def post(self, request):
        serializer = ArticleAnalyzeRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        url = serializer.validated_data["url"]
        summary_type = serializer.validated_data["summary_type"]

        try:
            article = extract_article_text(url)
        except ValueError as exc:
            return Response({
                "error": str(exc)
            }, status=400)

        prompt = build_article_summary_prompt(
            article["title"],
            article["text"],
            summary_type
        )
        summary = call_openai(prompt)

        return Response({
            "url": url,
            "title": article["title"],
            "summary_type": summary_type,
            "summary": summary
        })


class DocumentUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string"
                    },
                    "file": {
                        "type": "string",
                        "format": "binary"
                    },
                },
                "required": ["file"],
            }
        },
        responses={201: None}
    )
    def post(self, request):
        title = request.data.get("title")
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response({
                "error": "PDF 파일이 필요합니다."
            }, status=400)

        if not uploaded_file.name.lower().endswith(".pdf"):
            return Response({
                "error": "PDF 파일만 업로드할 수 있습니다."
            }, status=400)

        if not title:
            title = uploaded_file.name

        document = Document.objects.create(
            title=title,
            file=uploaded_file
        )

        pages_text = extract_text_from_pdf(document.file.path)

        chunks = []
        for page in pages_text:
            page_chunks = split_text(page["text"]) 

            print("\n" + "=" * 60)
            print(f"[CHUNK DEBUG] 페이지: {page['page']}")
            print(f"생성된 chunk 수: {len(page_chunks)}")

            for index, chunk_text in enumerate(page_chunks):
                print(
                    f"chunk {index}: "
                    f"길이={len(chunk_text)}, "
                    f"앞부분={chunk_text[:100]!r}"
                )

            print("=" * 60)

            for chunk_number, text in enumerate(page_chunks):
                chunks.append({
                    "text": text,
                    "page": page["page"],
                    "chunk": chunk_number
                })

        saved_chunk_count = save_chunks_to_chroma(
            document_id=document.id,
            file_name=uploaded_file.name,
            chunks=chunks
        )

        preview_text = ""
        if pages_text:
            preview_text = pages_text[0]["text"][:500]

        return Response({
            "message": "파일 업로드 및 텍스트 추출 성공",
            "document": {
                "id": document.id,
                "title": document.title,
                "file_url": document.file.url,
                "uploaded_at": document.uploaded_at
            },
            "page_count": len(pages_text),
            "chunk_count": saved_chunk_count,
            "preview_text": preview_text
        }, status=201)


class DocumentTextAPIView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({
                "error": "문서를 찾을 수 없습니다."
            }, status=404)

        pages_text = extract_text_from_pdf(document.file.path)

        return Response({
            "document": {
                "id": document_id,
                "title": document.title,
            },
            "pages": pages_text
        })
