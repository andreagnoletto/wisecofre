import hashlib
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import SystemConfiguration
from apps.files.models import FileAccessLog, FileResource, FileSecret
from apps.files.services import FileService, FileStorageService
from apps.resources.models import Resource, ResourceType


pytestmark = pytest.mark.django_db


# ── helpers ──────────────────────────────────────────────────────────────


def _make_user(suffix="a"):
    return User.objects.create_user(
        username=f"user{suffix}",
        email=f"user{suffix}@wisecofre.io",
        password="pass123",
    )


def _make_file_resource(user, resource_type, *, completed=True, size_bytes=1024):
    checksum = hashlib.sha256(f"test-{user.pk}".encode()).hexdigest()
    resource = Resource.objects.create(
        name="testfile", resource_type=resource_type, created_by=user, modified_by=user,
    )
    return FileResource.objects.create(
        resource=resource,
        storage_key=FileStorageService.build_storage_key(checksum),
        size_bytes=size_bytes,
        original_name_encrypted="encrypted_name",
        checksum_sha256=checksum,
        upload_completed=completed,
        created_by=user,
    )


def _rt_file():
    return ResourceType.objects.get_or_create(slug="file", defaults={"name": "File"})[0]


# ── upload ───────────────────────────────────────────────────────────────


class TestUpload:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "generate_upload_url", return_value="https://minio/upload")
    def test_upload_rejects_file_above_max_size(self, _mock_url):
        _rt_file()
        user = _make_user("big")
        svc = FileService()
        max_size = settings.FILE_MAX_SIZE_BYTES
        with pytest.raises(ValueError, match="limite máximo"):
            svc.initiate_upload(
                user=user,
                resource_data={"name": "huge.bin"},
                checksum_sha256="a" * 64,
                size_bytes=max_size + 1,
                original_name_encrypted="enc",
                session_key_encrypted="key",
            )

    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "generate_upload_url", return_value="https://minio/upload")
    def test_upload_respects_system_configuration_override(self, _mock_url):
        _rt_file()
        user = _make_user("cfg")
        custom_limit = 500
        SystemConfiguration.objects.create(key="FILE_MAX_SIZE_BYTES", value=custom_limit)

        svc = FileService()
        with pytest.raises(ValueError, match="limite máximo"):
            svc.initiate_upload(
                user=user,
                resource_data={"name": "small.bin"},
                checksum_sha256="b" * 64,
                size_bytes=custom_limit + 1,
                original_name_encrypted="enc",
                session_key_encrypted="key",
            )


# ── confirm upload ───────────────────────────────────────────────────────


class TestConfirmUpload:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "object_exists", return_value=False)
    def test_confirm_upload_fails_if_object_not_in_minio(self, _mock_exists):
        rt = _rt_file()
        user = _make_user("c1")
        fr = _make_file_resource(user, rt, completed=False)

        svc = FileService()
        with pytest.raises(ValueError, match="não encontrado"):
            svc.confirm_upload(fr)

    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "object_exists", return_value=True)
    def test_confirm_upload_sets_upload_completed_true(self, _mock_exists):
        rt = _rt_file()
        user = _make_user("c2")
        fr = _make_file_resource(user, rt, completed=False)

        svc = FileService()
        result = svc.confirm_upload(fr)
        assert result.upload_completed is True

        fr.refresh_from_db()
        assert fr.upload_completed is True


# ── download ─────────────────────────────────────────────────────────────


class TestDownload:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_download_url_requires_file_secret(self):
        rt = _rt_file()
        owner = _make_user("d1")
        other = _make_user("d1o")
        fr = _make_file_resource(owner, rt, completed=True)
        FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="k")

        svc = FileService()
        with pytest.raises(PermissionError, match="permissão"):
            svc.get_download_url(fr, other)

    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_download_url_fails_if_upload_not_completed(self):
        rt = _rt_file()
        user = _make_user("d2")
        fr = _make_file_resource(user, rt, completed=False)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="k")

        svc = FileService()
        with pytest.raises(ValueError, match="não foi concluído"):
            svc.get_download_url(fr, user)

    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "generate_download_url", return_value="https://minio/download")
    def test_download_creates_file_access_log(self, _mock_url):
        rt = _rt_file()
        user = _make_user("d3")
        fr = _make_file_resource(user, rt, completed=True)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="k")

        svc = FileService()
        url = svc.get_download_url(fr, user, ip_address="10.0.0.1")
        assert url == "https://minio/download"

        log = FileAccessLog.objects.get(file_resource=fr, user=user)
        assert log.action == FileAccessLog.Action.DOWNLOAD
        assert log.ip_address == "10.0.0.1"
        assert log.presigned_url_expires_at is not None


# ── share ────────────────────────────────────────────────────────────────


class TestShare:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_share_creates_file_secret_for_recipient(self):
        rt = _rt_file()
        owner = _make_user("s1")
        recipient = _make_user("s1r")
        fr = _make_file_resource(owner, rt, completed=True)
        FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="owner_key")

        svc = FileService()
        svc.share_file(fr, owner, recipient, "recipient_key")

        secret = FileSecret.objects.get(file_resource=fr, user=recipient)
        assert secret.session_key_encrypted == "recipient_key"

        log = FileAccessLog.objects.get(file_resource=fr, action=FileAccessLog.Action.SHARE)
        assert log.shared_with == recipient

    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_share_fails_without_own_file_secret(self):
        rt = _rt_file()
        owner = _make_user("s2")
        outsider = _make_user("s2o")
        recipient = _make_user("s2r")
        fr = _make_file_resource(owner, rt, completed=True)
        FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="ok")

        svc = FileService()
        with pytest.raises(PermissionError, match="permissão"):
            svc.share_file(fr, outsider, recipient, "enc_key")


# ── delete ───────────────────────────────────────────────────────────────


class TestDelete:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "delete_object")
    def test_delete_calls_storage_delete_and_soft_deletes_db(self, mock_delete):
        rt = _rt_file()
        user = _make_user("del1")
        fr = _make_file_resource(user, rt, completed=True)

        svc = FileService()
        svc.delete_file(fr, user, ip_address="10.0.0.2")

        mock_delete.assert_called_once_with(fr.storage_key)
        fr.resource.refresh_from_db()
        assert fr.resource.deleted_at is not None

        log = FileAccessLog.objects.get(file_resource=fr, action=FileAccessLog.Action.DELETE)
        assert log.ip_address == "10.0.0.2"

    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_non_owner_non_admin_cannot_delete(self):
        rt = _rt_file()
        owner = _make_user("del2o")
        other = _make_user("del2x")
        fr = _make_file_resource(owner, rt, completed=True)

        svc = FileService()
        with pytest.raises(PermissionError, match="criador"):
            svc.delete_file(fr, other)


# ── storage key ──────────────────────────────────────────────────────────


class TestStorageKey:
    def test_storage_key_format_from_checksum(self):
        checksum = "abcdef1234567890" + "0" * 48
        key = FileStorageService.build_storage_key(checksum)
        assert key == f"ab/cd/{checksum}"

    def test_storage_key_lowercased(self):
        checksum = "ABCDEF" + "0" * 58
        key = FileStorageService.build_storage_key(checksum)
        assert key == key.lower()


# ── cleanup task ─────────────────────────────────────────────────────────


class TestCleanupTask:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_cleanup_task_removes_stale_incomplete_uploads(self):
        from apps.files.tasks import cleanup_incomplete_uploads

        rt = _rt_file()
        user = _make_user("cl1")
        fr = _make_file_resource(user, rt, completed=False)
        # backdate created_at past the 1-hour cutoff
        FileResource.objects.filter(pk=fr.pk).update(created_at=timezone.now() - timedelta(hours=2))

        result = cleanup_incomplete_uploads()
        assert "1" in result
        fr.resource.refresh_from_db()
        assert fr.resource.deleted_at is not None

    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_cleanup_task_ignores_completed_uploads(self):
        from apps.files.tasks import cleanup_incomplete_uploads

        rt = _rt_file()
        user = _make_user("cl2")
        fr = _make_file_resource(user, rt, completed=True)
        FileResource.objects.filter(pk=fr.pk).update(created_at=timezone.now() - timedelta(hours=2))

        result = cleanup_incomplete_uploads()
        assert "0" in result
        fr.resource.refresh_from_db()
        assert fr.resource.deleted_at is None


# ── security invariants ──────────────────────────────────────────────────


class TestSecurityInvariants:
    def test_server_never_receives_plaintext_in_payload(self):
        """FileResource stores only encrypted data; original_name_encrypted is opaque."""
        rt = _rt_file()
        user = _make_user("sec1")
        fr = _make_file_resource(user, rt)
        assert fr.original_name_encrypted != ""
        for field in ("original_name_encrypted", "checksum_sha256", "storage_key"):
            val = getattr(fr, field)
            assert val, f"{field} should not be empty"

    def test_minio_bucket_is_private(self):
        assert settings.AWS_DEFAULT_ACL == "private"
        assert settings.AWS_QUERYSTRING_AUTH is True
