import uuid

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class FileResource(BaseModel):
    """Metadados de um arquivo criptografado armazenado no MinIO. O conteúdo em claro NUNCA é conhecido pelo servidor."""

    class EncryptionVersion(models.TextChoices):
        OPENPGP_V1 = "openpgp-aes256gcm-v1", "OpenPGP + AES-256-GCM v1"

    resource = models.OneToOneField(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="file_resource",
    )
    storage_key = models.CharField(max_length=512, unique=True, db_index=True)
    size_bytes = models.BigIntegerField()
    original_name_encrypted = models.TextField()
    mime_category = models.CharField(
        max_length=32,
        choices=[
            ("document", "Documento"),
            ("image", "Imagem"),
            ("archive", "Arquivo compactado"),
            ("key", "Chave / Certificado"),
            ("spreadsheet", "Planilha"),
            ("other", "Outro"),
        ],
        default="other",
    )
    checksum_sha256 = models.CharField(max_length=64)
    encryption_version = models.CharField(
        max_length=32,
        choices=EncryptionVersion.choices,
        default=EncryptionVersion.OPENPGP_V1,
    )
    upload_completed = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_files",
    )

    class Meta:
        verbose_name = "Arquivo"
        verbose_name_plural = "Arquivos"
        indexes = [models.Index(fields=["upload_completed", "created_at"])]

    def __str__(self):
        return f"FileResource({self.id}) -> Resource({self.resource_id})"

    @property
    def size_mb(self):
        return round(self.size_bytes / (1024 * 1024), 2)


class FileSecret(BaseModel):
    """Chave de sessão AES-256 criptografada com a chave pública PGP de cada usuário."""

    file_resource = models.ForeignKey(
        FileResource, on_delete=models.CASCADE, related_name="secrets"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="file_secrets",
    )
    session_key_encrypted = models.TextField()

    class Meta:
        verbose_name = "Segredo de Arquivo"
        verbose_name_plural = "Segredos de Arquivo"
        unique_together = [("file_resource", "user")]


class FileAccessLog(BaseModel):
    """Auditoria granular de cada acesso a um arquivo."""

    class Action(models.TextChoices):
        UPLOAD = "UPLOAD", "Upload iniciado"
        UPLOAD_CONFIRMED = "UPLOAD_CONFIRMED", "Upload confirmado"
        DOWNLOAD = "DOWNLOAD", "Download (URL pré-assinada gerada)"
        DELETE = "DELETE", "Arquivo deletado"
        SHARE = "SHARE", "Arquivo compartilhado"
        REVOKE = "REVOKE", "Acesso revogado"

    file_resource = models.ForeignKey(
        FileResource, on_delete=models.CASCADE, related_name="access_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="file_access_logs",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    presigned_url_expires_at = models.DateTimeField(null=True, blank=True)
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_file_shares",
    )

    class Meta:
        verbose_name = "Log de Acesso a Arquivo"
        verbose_name_plural = "Logs de Acesso a Arquivos"
        indexes = [
            models.Index(fields=["file_resource", "created_at"]),
            models.Index(fields=["user", "action", "created_at"]),
        ]
