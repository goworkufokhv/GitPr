import logging
import os
import time
from pathlib import PurePosixPath

from django.conf import settings
from django.db import IntegrityError, transaction
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
from .article_utils import (
    ArticleExtractionError,
    ArticleParseError,
    extract_article_text,
)
from .utils import calculate_uploaded_file_hash, extract_text_from_pdf, split_text
from .vector_store import delete_document_from_chroma
from .rag import (
    build_article_summary_prompt,
    build_prompt,
    build_summary_prompt,
    call_openai,
    parse_article_detailed_summary,
)
from .vector_store import save_chunks_to_chroma, search_chroma


logger = logging.getLogger(__name__)
ARTICLE_ERROR_MESSAGE = "기사가 아니거나 해당 기사의 본문을 추출할 수 없습니다."
TEST_PARSE_ERROR_URL = "test://parse-error"


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
        document_list = []

        for document in documents:
            try:
                file_exists = bool(
                    document.file
                    and os.path.exists(document.file.path)
                )
            except (OSError, ValueError):
                file_exists = False

            if not file_exists:
                logger.warning(
                    "[DocumentListAPIView]\n"
                    "missing media file:\n"
                    "document_id=%s\n"
                    "file=%s",
                    document.id,
                    document.file.name if document.file else "",
                )
                continue

            file_name = (
                PurePosixPath(document.file.name).name
                if document.file
                else ""
            )
            file_url = (
                request.build_absolute_uri(document.file.url)
                if document.file
                else None
            )

            document_list.append({
                "id": document.id,
                "title": document.title,
                "file_name": file_name,
                "file_url": file_url,
                "uploaded_at": document.uploaded_at
            })

        return Response({
            "documents": document_list
        })


class DocumentDeleteAPIView(APIView):
    def delete(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            logger.warning(
                "[Document Delete] stage=database_lookup status=failed "
                "document_id=%s reason=not_found",
                document_id,
            )
            return Response({
                "error": "문서를 찾을 수 없습니다."
            }, status=404)

        try:
            chroma_result = delete_document_from_chroma(document_id)
        except Exception:
            logger.exception(
                "[Document Delete] stage=chroma status=failed document_id=%s",
                document_id,
            )
            return Response({
                "error": "ChromaDB 문서 데이터 삭제에 실패했습니다."
            }, status=500)

        if chroma_result["remaining_count"] != 0:
            logger.error(
                "[Document Delete] stage=chroma status=failed "
                "document_id=%s remaining_count=%s",
                document_id,
                chroma_result["remaining_count"],
            )
            return Response({
                "error": "ChromaDB 문서 데이터 삭제에 실패했습니다."
            }, status=500)

        logger.info(
            "[Document Delete] stage=chroma status=success "
            "document_id=%s deleted_count=%s",
            document_id,
            chroma_result["deleted_count"],
        )

        if document.file:
            file_name = document.file.name
            storage = document.file.storage
            try:
                if storage.exists(file_name):
                    document.file.delete(save=False)
                    if storage.exists(file_name):
                        raise RuntimeError("Media file remains after deletion")
                    logger.info(
                        "[Document Delete] stage=media status=success "
                        "document_id=%s file=%s",
                        document_id,
                        file_name,
                    )
                else:
                    logger.warning(
                        "[Document Delete] stage=media status=already_missing "
                        "document_id=%s file=%s",
                        document_id,
                        file_name,
                    )
            except Exception:
                logger.exception(
                    "[Document Delete] stage=media status=failed "
                    "document_id=%s file=%s",
                    document_id,
                    file_name,
                )
                return Response({
                    "error": "PDF 파일 삭제에 실패했습니다."
                }, status=500)
        else:
            logger.info(
                "[Document Delete] stage=media status=already_missing "
                "document_id=%s file=",
                document_id,
            )

        try:
            with transaction.atomic():
                document.delete()
                if Document.objects.filter(id=document_id).exists():
                    raise RuntimeError("Database record remains after deletion")
        except Exception:
            logger.exception(
                "[Document Delete] stage=database status=failed document_id=%s",
                document_id,
            )
            return Response({
                "error": "문서 삭제 중 오류가 발생했습니다."
            }, status=500)

        logger.info(
            "[Document Delete] stage=database status=success document_id=%s",
            document_id,
        )
        logger.info(
            "[Document Delete] status=completed document_id=%s "
            "deleted_chroma_chunks=%s",
            document_id,
            chroma_result["deleted_count"],
        )

        return Response({
            "message": "문서가 삭제되었습니다.",
            "document_id": document_id,
            "deleted_chroma_chunks": chroma_result["deleted_count"],
        }, status=200)


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
        request_started_at = time.perf_counter()
        serializer = ArticleAnalyzeRequestSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning("[Article Error] Invalid URL")
            return Response({
                "error": ARTICLE_ERROR_MESSAGE
            }, status=400)

        url = serializer.validated_data["url"].strip()
        summary_type = serializer.validated_data["summary_type"]

        try:
            # Development-only hook for verifying parse-error logging.
            if settings.DEBUG and url == TEST_PARSE_ERROR_URL:
                raise ArticleParseError(
                    "Intentional newspaper parse error for testing."
                )

            article = extract_article_text(url)
        except ArticleParseError:
            logger.exception("[Article Error] Newspaper Parse Error")
            return Response({
                "error": ARTICLE_ERROR_MESSAGE
            }, status=400)
        except ArticleExtractionError:
            return Response({
                "error": ARTICLE_ERROR_MESSAGE
            }, status=400)
        except Exception:
            logger.exception("[Article Error] Newspaper Parse Error")
            return Response({
                "error": ARTICLE_ERROR_MESSAGE
            }, status=400)

        article_title = article.get("title") or ""
        article_text = article["text"] or ""
        safe_title = article_title.replace("\n", " ").strip()
        logger.info(
            "[Article Length] summary_type=%s "
            "title_chars=%s body_chars=%s body_words=%s",
            summary_type,
            len(safe_title),
            len(article_text),
            len(article_text.split()),
        )

        article_text_for_prompt = article_text[:12000]
        prompt = build_article_summary_prompt(
            article_title,
            article_text_for_prompt,
            summary_type
        )
        logger.info(
            "[Article GPT Request] summary_type=%s input_chars=%s",
            summary_type,
            len(prompt),
        )
        gpt_started_at = time.perf_counter()
        summary = call_openai(prompt)
        if summary_type == "detailed":
            summary = parse_article_detailed_summary(summary)
        gpt_elapsed_ms = round(
            (time.perf_counter() - gpt_started_at) * 1000,
            2,
        )
        logger.info(
            "[Article GPT Complete] summary_type=%s elapsed_ms=%s",
            summary_type,
            gpt_elapsed_ms,
        )
        total_elapsed_ms = round(
            (time.perf_counter() - request_started_at) * 1000,
            2,
        )
        logger.info(
            "[Article Complete] "
            "summary_type=%s body_chars=%s total_ms=%s",
            summary_type,
            len(article_text),
            total_elapsed_ms,
        )

        return Response({
            "url": url,
            "title": article_title,
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
        responses={
            201: None,
            400: None,
            409: None,
        }
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

        file_hash = calculate_uploaded_file_hash(uploaded_file)
        existing_document = Document.objects.filter(
            file_hash=file_hash
        ).first()

        if existing_document:
            logger.warning(
                "[Upload Duplicate] document_id=%s file_name=%s file_hash=%s",
                existing_document.id,
                uploaded_file.name,
                file_hash,
            )
            return Response({
                "error": "이미 있는 파일입니다.",
                "document": {
                    "id": existing_document.id,
                    "title": existing_document.title,
                },
            }, status=409)

        if not title:
            title = uploaded_file.name

        document = Document(
            title=title,
            file=uploaded_file,
            file_hash=file_hash,
        )

        try:
            with transaction.atomic():
                document.save(force_insert=True)
        except IntegrityError:
            # A concurrent request can store a file before losing the unique
            # hash race. Remove only the file stored by this request.
            if document.file and document.file.name:
                try:
                    document.file.delete(save=False)
                except Exception:
                    logger.exception(
                        "Failed to clean up duplicate upload file=%s",
                        document.file.name,
                    )

            existing_document = Document.objects.filter(
                file_hash=file_hash
            ).first()
            logger.warning(
                "[Upload Duplicate] document_id=%s file_name=%s file_hash=%s",
                existing_document.id if existing_document else None,
                uploaded_file.name,
                file_hash,
            )
            return Response({
                "error": "이미 있는 파일입니다.",
                "document": {
                    "id": (
                        existing_document.id
                        if existing_document
                        else None
                    ),
                    "title": (
                        existing_document.title
                        if existing_document
                        else None
                    ),
                },
            }, status=409)

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
