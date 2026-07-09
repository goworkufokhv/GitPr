# api/serializers.py

from rest_framework import serializers

class DocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    file = serializers.FileField(required=True)


class ChatRequestSerializer(serializers.Serializer):
    question = serializers.CharField(required=True)


class SummaryRequestSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(required=True)
    summary_type = serializers.ChoiceField(
        choices=["short", "detailed", "keywords"],
        required=False,
        default="short"
    )


class ArticleAnalyzeRequestSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    summary_type = serializers.ChoiceField(
        choices=["short", "detailed", "keywords"],
        required=False,
        default="short"
    )
