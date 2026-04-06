from rest_framework import serializers

from .models import FileAccessLog, FileResource, FileSecret


class FileUploadInitSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    checksum_sha256 = serializers.CharField(max_length=64)
    size_bytes = serializers.IntegerField(min_value=1)
    original_name_encrypted = serializers.CharField()
    session_key_encrypted = serializers.CharField()
    mime_category = serializers.ChoiceField(
        choices=[
            ("document", "Documento"),
            ("image", "Imagem"),
            ("archive", "Arquivo compactado"),
            ("key", "Chave / Certificado"),
            ("spreadsheet", "Planilha"),
            ("other", "Outro"),
        ],
        default="other",
        required=False,
    )
    folder_id = serializers.UUIDField(required=False, allow_null=True)


class FileResourceSerializer(serializers.ModelSerializer):
    size_mb = serializers.FloatField(read_only=True)

    class Meta:
        model = FileResource
        fields = [
            "id",
            "resource_id",
            "size_bytes",
            "size_mb",
            "mime_category",
            "checksum_sha256",
            "encryption_version",
            "upload_completed",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class FileConfirmSerializer(serializers.Serializer):
    pass


class FileShareRecipientSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    session_key_encrypted = serializers.CharField()
    permission_type = serializers.IntegerField(default=1)


class FileShareSerializer(serializers.Serializer):
    recipients = FileShareRecipientSerializer(many=True)


class FileSecretSerializer(serializers.ModelSerializer):
    original_name_encrypted = serializers.CharField(
        source="file_resource.original_name_encrypted", read_only=True
    )

    class Meta:
        model = FileSecret
        fields = ["session_key_encrypted", "original_name_encrypted"]
        read_only_fields = fields


class FileAccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileAccessLog
        fields = [
            "id",
            "file_resource",
            "user",
            "action",
            "ip_address",
            "user_agent",
            "presigned_url_expires_at",
            "shared_with",
            "created_at",
        ]
        read_only_fields = fields
