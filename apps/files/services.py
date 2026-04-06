"""FileService — toda a lógica de negócio do módulo files."""
from datetime import timedelta
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import User
    from .models import FileResource


class FileStorageService:
    """Wrapper de baixo nível para operações no MinIO/S3."""

    def __init__(self):
        self._client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4'),
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME

    def generate_upload_url(self, storage_key: str) -> str:
        return self._client.generate_presigned_url(
            'put_object',
            Params={'Bucket': self.bucket, 'Key': storage_key, 'ContentType': 'application/octet-stream'},
            ExpiresIn=settings.MINIO_UPLOAD_URL_EXPIRY_SECONDS,
        )

    def generate_download_url(self, storage_key: str) -> str:
        return self._client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': storage_key},
            ExpiresIn=settings.MINIO_PRESIGNED_URL_EXPIRY_SECONDS,
        )

    def delete_object(self, storage_key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=storage_key)

    def object_exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except self._client.exceptions.ClientError:
            return False

    @staticmethod
    def build_storage_key(checksum_sha256: str) -> str:
        h = checksum_sha256.lower()
        return f"{h[:2]}/{h[2:4]}/{h}"


class FileService:
    """Lógica de negócio de alto nível para o módulo files."""

    def __init__(self):
        self.storage = FileStorageService()

    def get_max_file_size(self) -> int:
        from apps.core.models import SystemConfiguration
        try:
            config = SystemConfiguration.objects.get(key='FILE_MAX_SIZE_BYTES')
            return int(config.value)
        except SystemConfiguration.DoesNotExist:
            return settings.FILE_MAX_SIZE_BYTES

    def initiate_upload(self, user, resource_data, checksum_sha256, size_bytes, original_name_encrypted, session_key_encrypted, mime_category='other'):
        from apps.resources.models import Resource, ResourceType
        from .models import FileResource, FileSecret

        max_size = self.get_max_file_size()
        if size_bytes > max_size:
            raise ValueError(f"Arquivo excede o limite máximo de {max_size // (1024 * 1024)} MB.")

        storage_key = FileStorageService.build_storage_key(checksum_sha256)
        resource_type = ResourceType.objects.get(slug='file')
        resource = Resource.objects.create(
            name=resource_data['name'], resource_type=resource_type,
            created_by=user, modified_by=user, folder_id=resource_data.get('folder_id'),
        )
        file_resource = FileResource.objects.create(
            resource=resource, storage_key=storage_key, size_bytes=size_bytes,
            original_name_encrypted=original_name_encrypted, mime_category=mime_category,
            checksum_sha256=checksum_sha256, upload_completed=False, created_by=user,
        )
        FileSecret.objects.create(file_resource=file_resource, user=user, session_key_encrypted=session_key_encrypted)
        upload_url = self.storage.generate_upload_url(storage_key)
        return file_resource, upload_url

    def confirm_upload(self, file_resource):
        if not self.storage.object_exists(file_resource.storage_key):
            raise ValueError("Arquivo ainda não encontrado no storage. Tente novamente.")
        file_resource.upload_completed = True
        file_resource.save(update_fields=['upload_completed', 'modified_at'])
        return file_resource

    def get_download_url(self, file_resource, user, ip_address='0.0.0.0'):
        from .models import FileAccessLog
        if not file_resource.secrets.filter(user=user).exists():
            raise PermissionError("Sem permissão para acessar este arquivo.")
        if not file_resource.upload_completed:
            raise ValueError("Upload ainda não foi concluído.")
        url = self.storage.generate_download_url(file_resource.storage_key)
        FileAccessLog.objects.create(
            file_resource=file_resource, user=user, action=FileAccessLog.Action.DOWNLOAD,
            ip_address=ip_address,
            presigned_url_expires_at=timezone.now() + timedelta(seconds=settings.MINIO_PRESIGNED_URL_EXPIRY_SECONDS),
        )
        return url

    def share_file(self, file_resource, from_user, to_user, session_key_encrypted_for_recipient, permission_type=1, ip_address='0.0.0.0'):
        from .models import FileSecret, FileAccessLog
        from apps.sharing.models import Permission
        if not file_resource.secrets.filter(user=from_user).exists():
            raise PermissionError("Sem permissão para compartilhar este arquivo.")
        FileSecret.objects.update_or_create(
            file_resource=file_resource, user=to_user,
            defaults={'session_key_encrypted': session_key_encrypted_for_recipient},
        )
        Permission.objects.update_or_create(
            aco='FileResource', aco_foreign_key=file_resource.id,
            aro='User', aro_foreign_key=to_user.id,
            defaults={'type': permission_type, 'created_by': from_user},
        )
        FileAccessLog.objects.create(
            file_resource=file_resource, user=from_user, action=FileAccessLog.Action.SHARE,
            ip_address=ip_address, shared_with=to_user,
        )

    def delete_file(self, file_resource, user, ip_address='0.0.0.0'):
        from .models import FileAccessLog
        if file_resource.created_by != user and not user.is_admin:
            raise PermissionError("Apenas o criador pode deletar este arquivo.")
        self.storage.delete_object(file_resource.storage_key)
        FileAccessLog.objects.create(
            file_resource=file_resource, user=user, action=FileAccessLog.Action.DELETE, ip_address=ip_address,
        )
        file_resource.resource.delete()
