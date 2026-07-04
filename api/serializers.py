# api/serializers.py

from rest_framework import serializers

class DocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    file = serializers.FileField(required=True)