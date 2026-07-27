from django.db import models

class Document(models.Model):
    title=models.CharField(max_length=100)
    file=models.FileField(upload_to="documents/")
    file_hash=models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    uploaded_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
