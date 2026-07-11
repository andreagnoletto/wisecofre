import pytest

from apps.accounts.models import User
from apps.files.models import FileResource, FileSecret
from apps.folders.models import Folder
from apps.groups.models import Group, GroupUser
from apps.resources.models import Resource, ResourceType, Secret
from apps.sharing.models import Permission
from apps.sharing.services import SharingService


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", email="owner@x.io", password="x")


@pytest.fixture
def member_a(db):
    return User.objects.create_user(username="ma", email="ma@x.io", password="x")


@pytest.fixture
def member_b(db):
    return User.objects.create_user(username="mb", email="mb@x.io", password="x")


@pytest.fixture
def outsider(db):
    return User.objects.create_user(username="out", email="out@x.io", password="x")


def make_group(owner, *members, admin=True):
    group = Group.objects.create(name=f"g-{owner.pk}", created_by=owner)
    GroupUser.objects.create(group=group, user=owner, is_admin=admin)
    for m in members:
        GroupUser.objects.create(group=group, user=m)
    return group


def make_password(owner, data="s3cr3t"):
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(name="p", resource_type=rt, created_by=owner)
    Secret.objects.create(resource=resource, user=owner, data=data)
    return resource


def make_file(owner):
    rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    resource = Resource.objects.create(name="f", resource_type=rt, created_by=owner)
    fr = FileResource.objects.create(
        resource=resource, storage_key=f"k/{owner.pk}", size_bytes=1,
        original_name_encrypted="f.txt", mime_category="document",
        checksum_sha256="abc", upload_completed=True, created_by=owner,
    )
    FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="local-storage")
    return fr


# ── password sharing with groups ────────────────────────────────────────────

def test_share_password_with_group_creates_group_permission(owner, member_a):
    group = make_group(owner, member_a)
    resource = make_password(owner)

    SharingService.share_password_with_group(resource, group, Permission.READ, owner)

    assert Permission.objects.filter(
        aco="Resource", aco_foreign_key=resource.pk,
        aro="Group", aro_foreign_key=group.pk,
    ).exists()


def test_group_member_receives_secret_with_owner_data(owner, member_a):
    group = make_group(owner, member_a)
    resource = make_password(owner, data="top-secret")

    SharingService.share_password_with_group(resource, group, Permission.READ, owner)

    secret = Secret.objects.get(resource=resource, user=member_a)
    assert secret.data == "top-secret"


def test_owner_is_never_duplicated_or_removed(owner, member_a):
    group = make_group(owner, member_a)
    resource = make_password(owner, data="d")

    SharingService.share_password_with_group(resource, group, Permission.READ, owner)

    assert Secret.objects.filter(resource=resource, user=owner).count() == 1


def test_reconcile_is_idempotent(owner, member_a):
    group = make_group(owner, member_a)
    resource = make_password(owner)

    SharingService.share_password_with_group(resource, group, Permission.READ, owner)
    SharingService.reconcile_password_secrets(resource)
    SharingService.reconcile_password_secrets(resource)

    assert Secret.objects.filter(resource=resource).count() == 2  # owner + member_a


def test_removing_group_member_revokes_their_secret(owner, member_a):
    group = make_group(owner, member_a)
    resource = make_password(owner)
    SharingService.share_password_with_group(resource, group, Permission.READ, owner)
    assert Secret.objects.filter(resource=resource, user=member_a).exists()

    GroupUser.objects.filter(group=group, user=member_a).delete()
    SharingService.on_group_membership_changed(group)

    assert not Secret.objects.filter(resource=resource, user=member_a).exists()


def test_direct_share_survives_group_reconcile(owner, member_a):
    # member_a has a direct share AND is in a group that is NOT shared with
    resource = make_password(owner, data="d")
    Permission.objects.create(
        aco="Resource", aco_foreign_key=resource.pk,
        aro="User", aro_foreign_key=member_a.pk, type=Permission.READ, created_by=owner,
    )
    Secret.objects.create(resource=resource, user=member_a, data="d")

    SharingService.reconcile_password_secrets(resource)

    assert Secret.objects.filter(resource=resource, user=member_a).exists()


def test_adding_member_backfills_existing_group_shares(owner, member_a, member_b):
    group = make_group(owner, member_a)
    resource = make_password(owner, data="d")
    SharingService.share_password_with_group(resource, group, Permission.READ, owner)
    assert not Secret.objects.filter(resource=resource, user=member_b).exists()

    GroupUser.objects.create(group=group, user=member_b)
    SharingService.on_group_membership_changed(group)

    assert Secret.objects.filter(resource=resource, user=member_b).exists()


# ── file sharing with groups ────────────────────────────────────────────────

def test_share_file_with_group_fans_out_file_secret(owner, member_a):
    group = make_group(owner, member_a)
    fr = make_file(owner)

    SharingService.share_file_with_group(fr, group, Permission.READ, owner)

    assert FileSecret.objects.filter(file_resource=fr, user=member_a).exists()
    assert Permission.objects.filter(
        aco="FileResource", aco_foreign_key=fr.pk, aro="Group", aro_foreign_key=group.pk,
    ).exists()


def test_removing_member_revokes_file_secret(owner, member_a):
    group = make_group(owner, member_a)
    fr = make_file(owner)
    SharingService.share_file_with_group(fr, group, Permission.READ, owner)

    GroupUser.objects.filter(group=group, user=member_a).delete()
    SharingService.on_group_membership_changed(group)

    assert not FileSecret.objects.filter(file_resource=fr, user=member_a).exists()


# ── folder sharing cascade ──────────────────────────────────────────────────

def test_share_folder_grants_access_to_contained_password(owner, member_a):
    group = make_group(owner, member_a)
    folder = Folder.objects.create(name="F", created_by=owner)
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(name="p", resource_type=rt, created_by=owner, folder=folder)
    Secret.objects.create(resource=resource, user=owner, data="d")

    SharingService.share_folder_with_group(folder, group, Permission.READ, owner)

    assert Secret.objects.filter(resource=resource, user=member_a).exists()


def test_share_folder_grants_access_to_contained_file(owner, member_a):
    group = make_group(owner, member_a)
    folder = Folder.objects.create(name="F", created_by=owner)
    rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    resource = Resource.objects.create(name="f", resource_type=rt, created_by=owner, folder=folder)
    fr = FileResource.objects.create(
        resource=resource, storage_key="k/z", size_bytes=1, original_name_encrypted="f",
        mime_category="document", checksum_sha256="z", upload_completed=True, created_by=owner,
    )
    FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="local-storage")

    SharingService.share_folder_with_group(folder, group, Permission.READ, owner)

    assert FileSecret.objects.filter(file_resource=fr, user=member_a).exists()
