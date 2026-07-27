from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q

from api.models import Document
from api.utils import calculate_uploaded_file_hash


class Command(BaseCommand):
    help = "Populate SHA-256 hashes for existing Document files."

    def handle(self, *args, **options):
        updated = 0
        skipped = 0
        duplicates = 0

        documents = Document.objects.filter(
            Q(file_hash__isnull=True) | Q(file_hash="")
        ).order_by("id")

        for document in documents.iterator():
            if (
                not document.file
                or not document.file.storage.exists(document.file.name)
            ):
                skipped += 1
                self.stdout.write(
                    f"Skipped missing file document_id={document.id}"
                )
                continue

            with document.file.open("rb"):
                file_hash = calculate_uploaded_file_hash(document.file)

            existing_document = Document.objects.filter(
                file_hash=file_hash
            ).exclude(id=document.id).first()

            if existing_document:
                duplicates += 1
                self.stdout.write(
                    "Duplicate hash detected:\n"
                    f"document_id={document.id}\n"
                    f"existing_document_id={existing_document.id}"
                )
                continue

            document.file_hash = file_hash
            try:
                with transaction.atomic():
                    document.save(update_fields=["file_hash"])
            except IntegrityError:
                existing_document = Document.objects.filter(
                    file_hash=file_hash
                ).exclude(id=document.id).first()
                duplicates += 1
                self.stdout.write(
                    "Duplicate hash detected:\n"
                    f"document_id={document.id}\n"
                    "existing_document_id="
                    f"{existing_document.id if existing_document else None}"
                )
                continue

            updated += 1
            self.stdout.write(f"Updated document_id={document.id}")

        self.stdout.write(
            "\nSummary:\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}\n"
            f"Duplicates: {duplicates}"
        )
