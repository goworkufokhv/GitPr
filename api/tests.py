import os
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .article_utils import (
    ArticleNetworkError,
    ArticleParseError,
    EmptyArticleBodyError,
    InvalidArticleUrlError,
    extract_article_text,
)
from .models import Document
from .rag import parse_article_detailed_summary
from .vector_store import (
    delete_document_from_chroma,
    get_all_chroma_document_ids,
)


class ArticleExtractionTests(TestCase):
    def test_invalid_url_is_rejected_and_logged(self):
        with self.assertLogs("api.article_utils", level="WARNING") as logs:
            with self.assertRaises(InvalidArticleUrlError):
                extract_article_text("ftp://example.com")

        self.assertIn("[Article Error] Invalid URL", logs.output[0])

    @patch("api.article_utils.requests.get")
    def test_network_error_is_classified_and_logged(self, mock_get):
        mock_get.side_effect = __import__("requests").ConnectionError()

        with self.assertLogs("api.article_utils", level="WARNING") as logs:
            with self.assertRaises(ArticleNetworkError):
                extract_article_text("https://example.com/article")

        self.assertIn("[Article Error] Network Error", logs.output[0])

    @patch("api.article_utils.requests.get")
    def test_empty_body_is_classified_and_logged(self, mock_get):
        mock_get.return_value.text = "<html><title>Example</title></html>"
        mock_get.return_value.raise_for_status.return_value = None

        with self.assertLogs("api.article_utils", level="WARNING") as logs:
            with self.assertRaises(EmptyArticleBodyError):
                extract_article_text("https://example.com/article")

        self.assertIn("[Article Error] Empty Article Body", logs.output[0])

    @patch("api.article_utils.BeautifulSoup", side_effect=RuntimeError("parse"))
    @patch("api.article_utils.requests.get")
    def test_parse_error_is_classified(self, mock_get, mock_soup):
        mock_get.return_value.text = "<html></html>"
        mock_get.return_value.raise_for_status.return_value = None

        with self.assertRaises(ArticleParseError):
            extract_article_text("https://example.com/article")


class ArticleAnalyzeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_invalid_url_returns_safe_error_message(self):
        response = self.client.post(
            "/api/articles/analyze/",
            {"url": "abc", "summary_type": "short"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "error": (
                    "기사가 아니거나 해당 기사의 본문을 "
                    "추출할 수 없습니다."
                )
            },
        )

    @override_settings(DEBUG=True)
    @patch("api.views.extract_article_text")
    def test_debug_parse_error_url_uses_common_error_response(
        self,
        mock_extract,
    ):
        with self.assertLogs("api.views", level="ERROR") as logs:
            response = self.client.post(
                "/api/articles/analyze/",
                {
                    "url": "  test://parse-error  ",
                    "summary_type": "short",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], (
            "기사가 아니거나 해당 기사의 본문을 추출할 수 없습니다."
        ))
        self.assertIn("[Article Error] Newspaper Parse Error", logs.output[0])
        self.assertIn(
            "Intentional newspaper parse error for testing.",
            logs.output[0],
        )
        self.assertIn("Traceback", logs.output[0])
        mock_extract.assert_not_called()

    @override_settings(DEBUG=False)
    def test_parse_error_url_is_invalid_when_debug_is_false(self):
        with self.assertLogs("api.article_utils", level="WARNING") as logs:
            response = self.client.post(
                "/api/articles/analyze/",
                {"url": "test://parse-error", "summary_type": "short"},
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("[Article Error] Invalid URL", logs.output[0])

    @patch(
        "api.views.time.perf_counter",
        side_effect=[1, 2, 6.18637, 6.93455],
    )
    @patch("api.views.call_openai", return_value="summary")
    @patch("api.views.extract_article_text")
    def test_success_logs_article_lengths_and_elapsed_times(
        self,
        mock_extract,
        mock_call_openai,
        mock_perf_counter,
    ):
        mock_extract.return_value = {
            "title": "Title\nwith newline",
            "text": "a" * 13000,
        }

        with self.assertLogs("api.views", level="INFO") as logs:
            response = self.client.post(
                "/api/articles/analyze/",
                {
                    "url": "https://example.com/article",
                    "summary_type": "short",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        combined_logs = "\n".join(logs.output)
        self.assertIn(
            '[Article Length] summary_type=short '
            "title_chars=18 body_chars=13000 body_words=1",
            combined_logs,
        )
        prompt = mock_call_openai.call_args.args[0]
        self.assertIn(
            f"[Article GPT Request] summary_type=short "
            f"input_chars={len(prompt)}",
            combined_logs,
        )
        self.assertIn(
            "[Article GPT Complete] summary_type=short elapsed_ms=4186.37",
            combined_logs,
        )
        self.assertIn(
            "[Article Complete] summary_type=short "
            "body_chars=13000 total_ms=5934.55",
            combined_logs,
        )
        self.assertNotIn("a" * 12001, prompt)

    @patch("api.views.call_openai")
    @patch("api.views.extract_article_text")
    def test_detailed_summary_returns_parsed_json(self, mock_extract, mock_openai):
        mock_extract.return_value = {"title": "Article", "text": "Body"}
        mock_openai.return_value = '''```json
{"title":"Article","introduction":"Intro","sections":[{"heading":"First","items":["One"]},{"heading":"Second","items":["Two"]}],"conclusion":"End"}
```'''

        response = self.client.post(
            "/api/articles/analyze/",
            {"url": "https://example.com/article", "summary_type": "detailed"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["sections"][1]["heading"], "Second")

    @patch("api.views.call_openai", return_value="legacy detailed summary")
    @patch("api.views.extract_article_text", return_value={"title": "Article", "text": "Body"})
    def test_detailed_summary_falls_back_to_raw_text(self, mock_extract, mock_openai):
        response = self.client.post(
            "/api/articles/analyze/",
            {"url": "https://example.com/article", "summary_type": "detailed"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], "legacy detailed summary")


class DetailedArticleSummaryParserTests(TestCase):
    def test_invalid_shape_falls_back_to_original_string(self):
        raw = '{"title": "Article", "sections": "invalid"}'
        self.assertEqual(parse_article_detailed_summary(raw), raw)


class FakeChromaCollection:
    def __init__(self, document_ids):
        self.document_ids = list(document_ids)

    def get(self, where=None, include=None):
        if where is None:
            return {
                "ids": [
                    f"chunk-{index}"
                    for index in range(len(self.document_ids))
                ],
                "metadatas": [
                    {"document_id": document_id}
                    for document_id in self.document_ids
                ],
            }

        target_id = where["document_id"]
        ids = [
            f"chunk-{index}"
            for index, document_id in enumerate(self.document_ids)
            if document_id == target_id
        ]
        return {"ids": ids, "metadatas": [{} for _ in ids]}

    def delete(self, where):
        target_id = where["document_id"]
        self.document_ids = [
            document_id
            for document_id in self.document_ids
            if document_id != target_id
        ]


class VectorStoreTests(TestCase):
    @patch("api.vector_store.get_collection")
    def test_get_all_chroma_document_ids_returns_valid_unique_integers(
        self,
        mock_get_collection,
    ):
        mock_collection = FakeChromaCollection([18, "18", 19])
        mock_collection.get = lambda include: {
            "metadatas": [
                {"document_id": 18},
                {"document_id": "18"},
                {"document_id": 19},
                {"document_id": None},
                {"document_id": "invalid"},
                None,
            ]
        }
        mock_get_collection.return_value = mock_collection

        self.assertEqual(get_all_chroma_document_ids(), {18, 19})

    @patch("api.vector_store.get_collection")
    def test_delete_document_from_chroma_removes_all_matching_chunks(
        self,
        mock_get_collection,
    ):
        fake_collection = FakeChromaCollection([999, 999, 1000])
        mock_get_collection.return_value = fake_collection

        result = delete_document_from_chroma("999")

        self.assertEqual(result["document_id"], 999)
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(result["remaining_count"], 0)
        self.assertEqual(
            fake_collection.get(where={"document_id": 999})["ids"],
            [],
        )


class DocumentApiTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.client = APIClient()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, title="Test document"):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile("test.pdf", b"%PDF-1.4 test"),
        )

    def test_list_excludes_document_with_missing_media_file(self):
        existing = self.create_document("Existing")
        missing = self.create_document("Missing")
        os.remove(missing.file.path)

        response = self.client.get("/api/documents/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["documents"]],
            [existing.id],
        )
        self.assertTrue(Document.objects.filter(id=missing.id).exists())

    @patch("api.views.save_chunks_to_chroma", return_value=1)
    @patch(
        "api.views.extract_text_from_pdf",
        return_value=[{"page": 1, "text": "PDF text"}],
    )
    def test_duplicate_pdf_content_returns_409_without_processing_again(
        self,
        mock_extract,
        mock_save_chunks,
    ):
        first_response = self.client.post(
            "/api/documents/upload/",
            {
                "title": "First title",
                "file": SimpleUploadedFile(
                    "original.pdf",
                    b"%PDF-1.4 identical content",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        media_files_after_first_upload = [
            path
            for path in os.listdir(os.path.join(self.media_root, "documents"))
        ]

        with self.assertLogs("api.views", level="WARNING") as logs:
            duplicate_response = self.client.post(
                "/api/documents/upload/",
                {
                    "title": "Different title",
                    "file": SimpleUploadedFile(
                        "renamed.pdf",
                        b"%PDF-1.4 identical content",
                        content_type="application/pdf",
                    ),
                },
                format="multipart",
            )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(
            duplicate_response.data,
            {
                "error": "이미 있는 파일입니다.",
                "document": {
                    "id": first_response.data["document"]["id"],
                    "title": "First title",
                },
            },
        )
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(
            os.listdir(os.path.join(self.media_root, "documents")),
            media_files_after_first_upload,
        )
        self.assertIn("[Upload Duplicate]", logs.output[0])
        self.assertEqual(mock_extract.call_count, 1)
        self.assertEqual(mock_save_chunks.call_count, 1)

    @patch("api.views.delete_document_from_chroma")
    def test_delete_removes_media_chroma_and_database_record(self, mock_delete):
        mock_delete.return_value = {
            "document_id": 1,
            "deleted_count": 3,
            "remaining_count": 0,
        }
        document = self.create_document()
        document_id = document.id
        file_path = document.file.path

        response = self.client.delete(f"/api/documents/{document_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["document_id"], document_id)
        self.assertEqual(response.data["deleted_chroma_chunks"], 3)
        self.assertFalse(os.path.exists(file_path))
        self.assertFalse(Document.objects.filter(id=document_id).exists())
        mock_delete.assert_called_once_with(document_id)

    @patch("api.views.delete_document_from_chroma")
    def test_delete_missing_media_still_removes_chroma_and_database_record(
        self,
        mock_delete,
    ):
        mock_delete.return_value = {
            "document_id": 1,
            "deleted_count": 2,
            "remaining_count": 0,
        }
        document = self.create_document()
        document_id = document.id
        os.remove(document.file.path)

        response = self.client.delete(f"/api/documents/{document_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.filter(id=document_id).exists())
        mock_delete.assert_called_once_with(document_id)

    @patch("api.views.delete_document_from_chroma")
    def test_chroma_failure_keeps_database_and_media(self, mock_delete):
        mock_delete.side_effect = RuntimeError("Chroma failed")
        document = self.create_document()
        document_id = document.id
        file_path = document.file.path

        response = self.client.delete(f"/api/documents/{document_id}/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data["error"],
            "ChromaDB 문서 데이터 삭제에 실패했습니다.",
        )
        self.assertTrue(Document.objects.filter(id=document_id).exists())
        self.assertTrue(os.path.exists(file_path))

    def test_delete_unknown_document_returns_json_404(self):
        response = self.client.delete("/api/documents/999999/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "문서를 찾을 수 없습니다.")


class CleanupMissingDocumentsCommandTests(TestCase):
    @patch(
        "api.management.commands.cleanup_missing_documents."
        "delete_document_from_chroma"
    )
    @patch(
        "api.management.commands.cleanup_missing_documents."
        "get_all_chroma_document_ids",
        return_value={18, 19, 20},
    )
    def test_dry_run_lists_chroma_only_ids_without_deleting(
        self,
        mock_get_ids,
        mock_delete,
    ):
        output = StringIO()

        call_command(
            "cleanup_missing_documents",
            "--dry-run",
            stdout=output,
        )

        self.assertIn("Chroma-only IDs: [18, 19, 20]", output.getvalue())
        self.assertIn("Chroma-only document IDs: 3", output.getvalue())
        mock_get_ids.assert_called_once_with()
        mock_delete.assert_not_called()
