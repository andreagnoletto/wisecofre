import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.files.models import FileResource, FileSecret
from apps.folders.models import Folder
from apps.groups.models import Group, GroupUser
from apps.resources.models import Resource, ResourceType, Secret


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="o", email="o@x.io", password="x", first_name="O")


@pytest.fixture
def member(db):
    return User.objects.create_user(username="m", email="m@x.io", password="x", first_name="M")


@pytest.fixture
def group(owner, member):
    g = Group.objects.create(name="Equipe", created_by=owner)
    GroupUser.objects.create(group=g, user=owner, is_admin=True)
    GroupUser.objects.create(group=g, user=member)
    return g


def make_password(owner, data="segredo"):
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    r = Resource.objects.create(name="p", resource_type=rt, created_by=owner)
    Secret.objects.create(resource=r, user=owner, data=data)
    return r


def make_file(owner):
    rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    r = Resource.objects.create(name="f", resource_type=rt, created_by=owner)
    fr = FileResource.objects.create(
        resource=r, storage_key=f"k/{owner.pk}", size_bytes=1, original_name_encrypted="f.txt",
        mime_category="document", checksum_sha256="c", upload_completed=True, created_by=owner,
    )
    FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="local-storage")
    return fr


def test_password_share_with_group_grants_member_access(owner, member, group):
    resource = make_password(owner, data="segredo")
    client = Client()
    client.force_login(owner)

    resp = client.post(
        reverse("password_share", args=[resource.pk]),
        {"share_type": "group", "group_id": str(group.pk), "permission": "read"},
    )

    assert resp.status_code == 302
    member_secret = Secret.objects.get(resource=resource, user=member)
    assert member_secret.data == "segredo"

    # member can now open the password detail page
    member_client = Client()
    member_client.force_login(member)
    detail = member_client.get(reverse("password_detail", args=[resource.pk]))
    assert detail.status_code == 200


def test_file_share_with_group_grants_member_access(owner, member, group):
    fr = make_file(owner)
    client = Client()
    client.force_login(owner)

    resp = client.post(
        reverse("file_share", args=[fr.pk]),
        {"share_type": "group", "group_id": str(group.pk), "permission": "read"},
    )

    assert resp.status_code == 302
    assert FileSecret.objects.filter(file_resource=fr, user=member).exists()

    # owner detail page renders the group-access card; member can open the file
    assert client.get(reverse("file_detail", args=[fr.pk])).status_code == 200
    member_client = Client()
    member_client.force_login(member)
    assert member_client.get(reverse("file_detail", args=[fr.pk])).status_code == 200


def test_folder_share_with_group_grants_access_to_folder_and_contents(owner, member, group):
    folder = Folder.objects.create(name="Cofre", created_by=owner)
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(name="p", resource_type=rt, created_by=owner, folder=folder)
    Secret.objects.create(resource=resource, user=owner, data="d")

    client = Client()
    client.force_login(owner)
    resp = client.post(
        reverse("folder_share", args=[folder.pk]),
        {"group_id": str(group.pk), "permission": "read"},
    )
    assert resp.status_code == 302

    # member gets access to the contained password ...
    assert Secret.objects.filter(resource=resource, user=member).exists()
    # ... and can open the folder page
    member_client = Client()
    member_client.force_login(member)
    assert member_client.get(reverse("folder_detail", args=[folder.pk])).status_code == 200


def test_removing_member_from_group_revokes_password_access(owner, member, group):
    resource = make_password(owner)
    client = Client()
    client.force_login(owner)
    client.post(
        reverse("password_share", args=[resource.pk]),
        {"share_type": "group", "group_id": str(group.pk), "permission": "read"},
    )
    assert Secret.objects.filter(resource=resource, user=member).exists()

    client.post(reverse("group_remove_member", args=[group.pk, member.pk]))

    assert not Secret.objects.filter(resource=resource, user=member).exists()


def test_unshare_group_revokes_access(owner, member, group):
    resource = make_password(owner)
    client = Client()
    client.force_login(owner)
    client.post(
        reverse("password_share", args=[resource.pk]),
        {"share_type": "group", "group_id": str(group.pk), "permission": "read"},
    )
    assert Secret.objects.filter(resource=resource, user=member).exists()

    client.post(reverse("password_unshare_group", args=[resource.pk]), {"group_id": str(group.pk)})

    assert not Secret.objects.filter(resource=resource, user=member).exists()
