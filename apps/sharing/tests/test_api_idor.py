import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.folders.models import Folder
from apps.resources.models import Resource, ResourceType, Secret
from apps.sharing.models import Permission


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="o", email="o@x.io", password="x")


@pytest.fixture
def attacker(db):
    return User.objects.create_user(username="atk", email="atk@x.io", password="x")


@pytest.fixture
def victim(db):
    return User.objects.create_user(username="vic", email="vic@x.io", password="x")


def make_password(owner, data="segredo"):
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(name="p", resource_type=rt, created_by=owner)
    Secret.objects.create(resource=resource, user=owner, data=data)
    return resource


def test_share_resource_denies_non_owner(owner, attacker, victim):
    resource = make_password(owner)
    client = APIClient()
    client.force_authenticate(user=attacker)  # attacker não tem acesso ao recurso

    resp = client.post(
        f"/api/v1/share/resource/{resource.pk}/",
        {"recipients": [{"user_id": str(victim.pk), "secret_data": "injetado"}]},
        format="json",
    )

    assert resp.status_code in (403, 404)
    assert not Permission.objects.filter(
        aco="Resource", aco_foreign_key=resource.pk, aro_foreign_key=victim.pk
    ).exists()
    assert not Secret.objects.filter(resource=resource, user=victim).exists()


def test_share_resource_ignores_attacker_supplied_secret_data(owner, victim):
    resource = make_password(owner, data="segredo-real")
    client = APIClient()
    client.force_authenticate(user=owner)  # dono pode compartilhar

    resp = client.post(
        f"/api/v1/share/resource/{resource.pk}/",
        {"recipients": [{"user_id": str(victim.pk), "secret_data": "veneno"}]},
        format="json",
    )

    assert resp.status_code == 201
    # o segredo do destinatário vem do dono, nunca do secret_data arbitrário
    assert Secret.objects.get(resource=resource, user=victim).data == "segredo-real"


def test_share_folder_denies_non_owner(owner, attacker, victim):
    folder = Folder.objects.create(name="F", created_by=owner)
    client = APIClient()
    client.force_authenticate(user=attacker)

    resp = client.post(
        f"/api/v1/share/folder/{folder.pk}/",
        {"recipients": [{"user_id": str(victim.pk)}]},
        format="json",
    )

    assert resp.status_code in (403, 404)
    assert not Permission.objects.filter(
        aco="Folder", aco_foreign_key=folder.pk
    ).exists()
