import importlib

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.accounts.models import User
from apps.resources.models import Resource, ResourceType, Secret, SecretHistory


def _load_encrypt_migration():
    return importlib.import_module("apps.resources.migrations.0003_encrypt_existing_secrets")


def _password(user, data):
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(name="p", resource_type=rt, created_by=user)
    return Secret.objects.create(resource=resource, user=user, data=data)


def test_secret_data_is_encrypted_at_rest(db):
    user = User.objects.create_user(username="u", email="u@x.io", password="x")
    secret = _password(user, "super-secret-value")

    # ORM devolve o valor claro (transparente)
    assert Secret.objects.get(pk=secret.pk).data == "super-secret-value"

    # ... mas no banco está cifrado, sem o texto claro
    with connection.cursor() as cur:
        cur.execute("SELECT data FROM resources_secret LIMIT 1")
        raw = cur.fetchone()[0]
    assert raw.startswith("fernet:")
    assert "super-secret-value" not in raw


def test_migration_encrypts_legacy_plaintext_rows(db, settings):
    settings.ENCRYPTION_KEY = "chave-de-teste-permanente"  # guard exige chave explícita
    user = User.objects.create_user(username="mig", email="mig@x.io", password="x")
    secret = _password(user, "qualquer")
    # simula dado legado em texto puro (grava direto na coluna, sem passar pelo field)
    with connection.cursor() as cur:
        cur.execute("UPDATE resources_secret SET data = %s", ["plain-legacy"])
    assert Secret.objects.get(pk=secret.pk).data == "plain-legacy"  # passa direto

    _load_encrypt_migration().encrypt_existing(django_apps, None)

    # agora está cifrado no banco, mas o ORM ainda devolve o valor original
    with connection.cursor() as cur:
        cur.execute("SELECT data FROM resources_secret LIMIT 1")
        raw = cur.fetchone()[0]
    assert raw.startswith("fernet:")
    assert Secret.objects.get(pk=secret.pk).data == "plain-legacy"


def test_migration_aborts_without_key_when_data_exists(db, settings):
    """Proteção contra lockout: com dados e sem ENCRYPTION_KEY, a migração aborta."""
    settings.ENCRYPTION_KEY = ""
    user = User.objects.create_user(username="mig2", email="mig2@x.io", password="x")
    _password(user, "qualquer")

    with pytest.raises(RuntimeError):
        _load_encrypt_migration().encrypt_existing(django_apps, None)


def test_secret_history_data_is_encrypted_at_rest(db):
    user = User.objects.create_user(username="u2", email="u2@x.io", password="x")
    secret = _password(user, "v1")
    hist = SecretHistory.objects.create(secret=secret, data="old-secret", created_by=user)

    assert SecretHistory.objects.get(pk=hist.pk).data == "old-secret"
    with connection.cursor() as cur:
        cur.execute("SELECT data FROM resources_secrethistory LIMIT 1")
        raw = cur.fetchone()[0]
    assert raw.startswith("fernet:")
    assert "old-secret" not in raw
