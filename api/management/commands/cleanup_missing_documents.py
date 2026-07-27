import os

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Document
from api.vector_store import (
    delete_document_from_chroma,
    get_all_chroma_document_ids,
)


class Command(BaseCommand):
    help = (
        "Remove documents whose media files are missing and ChromaDB data "
        "whose Document records no longer exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List missing documents without deleting them.",
        )

    def handle(self, *args, **options):
        documents = list(Document.objects.all())
        db_ids = {document.id for document in documents}
        chroma_ids = get_all_chroma_document_ids()
        chroma_only_ids = chroma_ids - db_ids
        missing_file_documents = []

        for document in documents:
            try:
                file_exists = bool(
                    document.file
                    and os.path.exists(document.file.path)
                )
            except (OSError, ValueError):
                file_exists = False

            if not file_exists:
                missing_file_documents.append(document)

        self.stdout.write(f"DB IDs: {sorted(db_ids)}")
        self.stdout.write(f"Chroma IDs: {sorted(chroma_ids)}")
        self.stdout.write(f"Chroma-only IDs: {sorted(chroma_only_ids)}")

        self.stdout.write("\nMissing media documents:")
        for document in missing_file_documents:
            self.stdout.write(
                f"- document_id={document.id} "
                f"title={document.title} "
                f"file={document.file.name if document.file else ''}"
            )

        self.stdout.write("\nChroma-only documents:")
        for document_id in sorted(chroma_only_ids):
            self.stdout.write(f"- document_id={document_id}")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run summary:\n"
                    f"Missing media documents: {len(missing_file_documents)}\n"
                    f"Chroma-only document IDs: {len(chroma_only_ids)}"
                )
            )
            return

        deleted_missing_media_count = 0
        deleted_chroma_only_count = 0
        deleted_chunk_count = 0
        failures = []

        for document in missing_file_documents:
            document_id = document.id
            try:
                chroma_result = delete_document_from_chroma(document_id)
                if chroma_result["remaining_count"] != 0:
                    raise RuntimeError(
                        "ChromaDB chunks remain after deletion: "
                        f"remaining_count={chroma_result['remaining_count']}"
                    )
                with transaction.atomic():
                    document.delete()
            except Exception as error:
                failures.append(("missing-media", document_id, str(error)))
                self.stderr.write(
                    self.style.ERROR(
                        "Failed missing-media "
                        f"document_id={document_id}: {error}"
                    )
                )
                continue

            deleted_missing_media_count += 1
            deleted_chunk_count += chroma_result["deleted_count"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted missing-media document_id={document_id}\n"
                    f"Deleted chunks={chroma_result['deleted_count']}\n"
                    f"Remaining chunks={chroma_result['remaining_count']}"
                )
            )

        for document_id in sorted(chroma_only_ids):
            try:
                chroma_result = delete_document_from_chroma(document_id)
                if chroma_result["remaining_count"] != 0:
                    raise RuntimeError(
                        "ChromaDB chunks remain after deletion: "
                        f"remaining_count={chroma_result['remaining_count']}"
                    )
            except Exception as error:
                failures.append(("chroma-only", document_id, str(error)))
                self.stderr.write(
                    self.style.ERROR(
                        "Failed Chroma-only "
                        f"document_id={document_id}: {error}"
                    )
                )
                continue

            deleted_chroma_only_count += 1
            deleted_chunk_count += chroma_result["deleted_count"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted Chroma-only document_id={document_id}\n"
                    f"Deleted chunks={chroma_result['deleted_count']}\n"
                    f"Remaining chunks={chroma_result['remaining_count']}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\nCleanup summary:\n"
                f"Deleted missing-media documents: {deleted_missing_media_count}\n"
                f"Deleted Chroma-only document IDs: {deleted_chroma_only_count}\n"
                f"Deleted Chroma chunks: {deleted_chunk_count}\n"
                f"Failed items: {len(failures)}"
            )
        )

        if failures:
            self.stderr.write("Failures:")
            for item_type, document_id, error in failures:
                self.stderr.write(
                    f"type={item_type} document_id={document_id}: {error}"
                )
