from django.urls import path
from .views import (
    TestAPIView,
    ChatAPIView,
    DocumentListAPIView,
    DocumentUploadAPIView,
    DocumentTextAPIView,
    SummaryAPIView,
)

urlpatterns = [#접속 경로에 따라 어떤 View로 보낼지 정하는 목록
    path("test/", TestAPIView.as_view()), #"test/" 주소로 요청이 들어오면 TestAPIView를 실행해라
    path("chat/", ChatAPIView.as_view()), #"chat/" 주소로 요청이 들어오면 ChatAPIView를 실행해라
    path("documents/", DocumentListAPIView.as_view()), #"documents/" 주소로 요청이 들어오면 DocumentListAPIView를 실행해라
    path("documents/upload/", DocumentUploadAPIView.as_view()),
    path("documents/<int:document_id>/text/", DocumentTextAPIView.as_view()),
    path("summary/", SummaryAPIView.as_view()),
]
