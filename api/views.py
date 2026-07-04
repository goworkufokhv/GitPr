from django.shortcuts import render #원래 Django에서 HTML 페이지를 보여줄 때 많이 써.(지금은 없어도 됨)
from rest_framework.views import APIView #API 요청을 처리하는 View를 만들기 위한 기본 틀
from rest_framework.response import Response #Django에서 JSON 응답을 쉽게 만들어주는 도구야.
from .models import Document
from .utils import extract_text_from_pdf, split_text
from .vector_store import save_chunks_to_chroma
from drf_spectacular.utils import extend_schema
from .serializers import DocumentUploadSerializer

class TestAPIView(APIView): #API 요청을 처리하는 View다.
    def get(self, request):
        return Response({
            "message": "Django REST API 연결 성공",
            "status": "ok"
        })
    
class ChatAPIView(APIView):
    def post(self, request): #POST 요청이 들어왔을 때 실행되는 함수야.
        question=request.data.get("question")
        document_id=request.data.get("document_id")

        if not question:
            return Response({
                "error": "Question 값이 필요합니다."
            },status=400) #status는 HTTP 상태 코드로, 서버가 요청 처리 결과를 숫자로 알려주는 방식이야.
        
        return Response({
            "answer": f"질문 내용: {question}",
            "document_id": document_id,
            "sources": [
                {
                    "file_name":"DB7장.pdf",
                    "page":17,
                    "similarity":0.92
                }
            ]
        })
    
class DocumentListAPIView(APIView): #왼쪽 사이드바의 자료 목록을 반환하는 API야.
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=DocumentUploadSerializer,
        responses={201: None}
    )
    def post(self, request):
        title = request.data.get("title")
        uploaded_file = request.FILES.get("file")
    def get(self,request):
        documents=[ #아직 데이터베이스에서 가져온 게 아니라, 코드 안에 직접 적어둔 가짜 자료 목록이야.
            {
                "id":1,
                "title": "DB 7장.pdf",
                "type": "pdf",
                "category":"데이터베이스",
                "selected":True
            },
            {
                "id":2,
                "title": "DB 8장.pdf",
                "type": "pdf",
                "category":"데이터베이스",
                "selected":False
            },
            {
                "id":3,
                "title": "1장.pdf",
                "type": "pdf",
                "category":"컴퓨터구조",
                "selected":False
            }
        ]

        return Response({
            "documents":documents
        })
    
from rest_framework.parsers import MultiPartParser, FormParser
    
class DocumentUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request): #이 API는 PDF 업로드용이기 때문에 POST를 사용해.
        title=request.data.get("title")
        uploaded_file=request.FILES.get("file")

        if not uploaded_file:
            return Response({
                "error":"PDF 파일이 필요합니다."
            },status=400)

        if not uploaded_file.name.lower().endswith(".pdf"):
            return Response({
                "error": "PDF 파일만 업로드할 수 있습니다."
            }, status=400)
        
        if not title:
            title=uploaded_file.name

        #업로드된 파일 정보를 DB에 저장하는 코드야.
        document=Document.objects.create(
            title=title,
            file=uploaded_file
        )

        #방금 저장한 PDF 파일에서 텍스트를 추출하는 코드야.
        pages_text=extract_text_from_pdf(document.file.path)

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

        preview_text=""
        if pages_text:
            preview_text=pages_text[0]["text"][:500]
            #첫 페이지 텍스트 중 앞부분 500자만 미리보기로 보여주는 코드야.

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
        },status=201)
    
class DocumentTextAPIView(APIView):
    #이 API는 이미 업로드된 문서의 텍스트를 확인하는 API야.
    def get(self, request, document_id):
        try:
            document=Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({
                "error": "문서를 찾을 수 없습니다."
            },status=404)
        
        pages_text=extract_text_from_pdf(document.file.path)

        return Response({
            "document":{
                "id": document_id,
                "title": document.title,
            },
            "pages":pages_text

        })
