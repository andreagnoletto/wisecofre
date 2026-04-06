import hashlib

import pytest

from apps.accounts.models import User
from apps.files.models import FileAccessLog, FileResource, FileSecret
from apps.files.services import FileStorageService
from apps.resources.models import Resource, ResourceType


pytestmark = pytest.mark.django_db


def _make_user(suffix="m"):
    return User.objects.create_user(
        username=f"model{suffix}", email=f"model{suffix}@wisecofre.io", password="pass123",
    )


def _rt_file():
    return ResourceType.objects.get_or_create(slug="file", defaults={"name": "File"})[0]


def _make_fr(user, rt, *, size_bytes=5_242_880):
    checksum = hashlib.sha256(f"model-{user.pk}".encode()).hexdigest()
    resource = Resource.objects.create(
        name="modelfile", resource_type=rt, created_by=user, modified_by=user,
    )
    return FileResource.objects.create(
        resource=resource,
        storage_key=FileStorageService.build_storage_key(checksum),
        size_bytes=size_bytes,
        original_name_encrypted="enc",
        checksum_sha256=checksum,
        upload_completed=True,
        created_by=user,
    )


class TestFileResourceModel:
    def test_file_resource_str_representation(self):
        rt = _rt_file()
        user = _make_user("str")
        fr = _make_fr(user, rt)
        expected = f"FileResource({fr.id}) -> Resource({fr.resource_id})"
        assert str(fr) == expected

    def test_file_resource_size_mb_property(self):
        rt = _rt_file()
        user = _make_user("mb")
        fr = _make_fr(user, rt, size_bytes=5_242_880)
        assert fr.size_mb == 5.0

        fr2 = _make_fr(_make_user("mb2"), rt, size_bytes=1_048_576)
        assert fr2.size_mb == 1.0

        fr3 = _make_fr(_make_user("mb3"), rt, size_bytes=512)
        assert fr3.size_mb == 0.0


class TestFileSecretModel:
    def test_file_secret_unique_together(self):
        rt = _rt_file()
        user = _make_user("unq")
        fr = _make_fr(user, rt)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="key1")

        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="key2")


class TestFileAccessLogModel:
    def test_file_access_log_creation(self):
        rt = _rt_file()
        user = _make_user("log")
        fr = _make_fr(user, rt)
        log = FileAccessLog.objects.create(
            file_resource=fr,
            user=user,
            action=FileAccessLog.Action.DOWNLOAD,
            ip_address="192.168.1.1",
        )
        assert log.pk is not None
        assert log.action == "DOWNLOAD"
        assert log.ip_address == "192.168.1.1"
        assert log.file_resource == fr
        assert log.user == user
