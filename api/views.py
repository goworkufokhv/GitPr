from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema

from .models import Document
from .utils import extract_text_from_pdf, split_text
from .vector_store import save_chunks_to_chroma


class TestAPIView(APIView):
    def get(self, request):
        return Response({
            "message": "Django REST API 연결 성공",
            "status": "ok"
        })


class ChatAPIView(APIView):
    def post(self, request):
        question = request.data.get("question")
        document_id = request.data.get("document_id")

        if not question:
            return Response({
                "error": "Question 값이 필요합니다."
            }, status=400)

        return Response({
            "answer": f"질문 내용: {question}",
            "document_id": document_id,
            "sources": [
                {
                    "file_name": "DB7장.pdf",
                    "page": 17,
                    "similarity": 0.92
                }
            ]
        })


class DocumentListAPIView(APIView):
    def get(self, request):
        documents = [
            {
                "id": 1,
                "title": "DB 7장.pdf",
                "type": "pdf",
                "category": "데이터베이스",
                "selected": True
            },
            {
                "id": 2,
                "title": "DB 8장.pdf",
                "type": "pdf",
                "category": "데이터베이스",
                "selected": False
            },
            {
                "id": 3,
                "title": "1장.pdf",
                "type": "pdf",
                "category": "컴퓨터구조",
                "selected": False
            }
        ]

        return Response({
            "documents": documents
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