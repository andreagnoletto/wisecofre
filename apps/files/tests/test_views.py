import hashlib
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.files.models import FileResource, FileSecret
from apps.files.services import FileStorageService
from apps.resources.models import Resource, ResourceType


pytestmark = pytest.mark.django_db


# ── helpers ──────────────────────────────────────────────────────────────

BASE_URL = "/api/v1/files/"


def _make_user(suffix="v"):
    return User.objects.create_user(
        username=f"view{suffix}", email=f"view{suffix}@wisecofre.io", password="pass123",
    )


def _rt_file():
    return ResourceType.objects.get_or_create(slug="file", defaults={"name": "File"})[0]


def _make_file_resource(user, rt, *, completed=True):
    checksum = hashlib.sha256(f"view-{user.pk}".encode()).hexdigest()
    resource = Resource.objects.create(
        name="viewfile", resource_type=rt, created_by=user, modified_by=user,
    )
    return FileResource.objects.create(
        resource=resource,
        storage_key=FileStorageService.build_storage_key(checksum),
        size_bytes=2048,
        original_name_encrypted="enc",
        checksum_sha256=checksum,
        upload_completed=completed,
        created_by=user,
    )


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── tests ────────────────────────────────────────────────────────────────


class TestListFiles:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_list_files_returns_only_accessible_files(self):
        rt = _rt_file()
        owner = _make_user("lst1")
        other = _make_user("lst2")
        fr = _make_file_resource(owner, rt)
        FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="k")

        client = _auth_client(other)
        resp = client.get(BASE_URL)
        assert resp.status_code == status.HTTP_200_OK
        ids = [r["id"] for r in resp.data["results"]]
        assert str(fr.id) not in ids

        client_owner = _auth_client(owner)
        resp = client_owner.get(BASE_URL)
        ids = [r["id"] for r in resp.data["results"]]
        assert str(fr.id) in ids


class TestUploadUrl:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "generate_upload_url", return_value="https://minio/up")
    def test_upload_url_endpoint_creates_file_resource(self, _mock_url):
        _rt_file()
        user = _make_user("up1")
        client = _auth_client(user)
        resp = client.post(
            f"{BASE_URL}upload-url/",
            {
                "name": "doc.pdf",
                "checksum_sha256": "c" * 64,
                "size_bytes": 4096,
                "original_name_encrypted": "enc_name",
                "session_key_encrypted": "enc_key",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "upload_url" in resp.data
        assert FileResource.objects.filter(created_by=user).exists()


class TestConfirmUpload:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "object_exists", return_value=True)
    def test_confirm_upload_endpoint(self, _mock_exists):
        rt = _rt_file()
        user = _make_user("conf1")
        fr = _make_file_resource(user, rt, completed=False)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="k")

        client = _auth_client(user)
        resp = client.post(f"{BASE_URL}{fr.pk}/confirm-upload/")
        assert resp.status_code == status.HTTP_200_OK
        fr.refresh_from_db()
        assert fr.upload_completed is True


class TestDownloadUrl:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "generate_download_url", return_value="https://minio/dl")
    def test_download_url_endpoint(self, _mock_url):
        rt = _rt_file()
        user = _make_user("dl1")
        fr = _make_file_resource(user, rt, completed=True)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="k")

        client = _auth_client(user)
        resp = client.get(f"{BASE_URL}{fr.pk}/download-url/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["download_url"] == "https://minio/dl"


class TestShareEndpoint:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    def test_share_endpoint(self):
        rt = _rt_file()
        owner = _make_user("sh1")
        recipient = _make_user("sh1r")
        fr = _make_file_resource(owner, rt)
        FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="k")

        client = _auth_client(owner)
        resp = client.post(
            f"{BASE_URL}{fr.pk}/share/",
            {
                "recipients": [
                    {
                        "user_id": str(recipient.pk),
                        "session_key_encrypted": "for_recipient",
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["shared"] is True
        assert FileSecret.objects.filter(file_resource=fr, user=recipient).exists()


class TestDeleteEndpoint:
    @patch.object(FileStorageService, "__init__", lambda self: None)
    @patch.object(FileStorageService, "delete_object")
    def test_delete_endpoint(self, _mock_del):
        rt = _rt_file()
        user = _make_user("del1v")
        fr = _make_file_resource(user, rt)
        FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="k")

        client = _auth_client(user)
        resp = client.delete(f"{BASE_URL}{fr.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        _mock_del.assert_called_once()


class TestAuth:
    def test_unauthenticated_access_returns_401(self):
        client = APIClient()
        resp = client.get(BASE_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
