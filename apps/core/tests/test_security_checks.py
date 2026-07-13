from io import StringIO

from django.core.management import call_command

from apps.core.checks import (
    check_weak_default_secrets,
    security_overall,
    security_status,
)


def _item(items, label):
    return next(i for i in items if i["label"] == label)


def test_security_status_ok_with_strong_encryption(settings):
    settings.DEBUG = False
    settings.SECRET_KEY = "forte-xyz"
    settings.ENCRYPTION_KEY = "forte-dedicada"

    items = security_status()

    assert _item(items, "Cifragem em repouso")["level"] == "ok"
    assert _item(items, "Chave do Django (SECRET_KEY)")["level"] == "ok"


def test_security_status_flags_weak_encryption(settings):
    settings.ENCRYPTION_KEY = "wc-encr1pt10n-k3y-ch4ng3-m3-2026"

    items = security_status()

    assert _item(items, "Cifragem em repouso")["level"] == "error"
    assert security_overall(items) == "error"


def test_security_status_never_exposes_values(settings):
    settings.SECRET_KEY = "valor-super-secreto-nao-vazar"
    settings.ENCRYPTION_KEY = "outro-segredo-nao-vazar"

    blob = " ".join(i["label"] + i["detail"] for i in security_status())

    assert "valor-super-secreto-nao-vazar" not in blob
    assert "outro-segredo-nao-vazar" not in blob


def test_generate_secrets_outputs_all_keys():
    out = StringIO()
    call_command("generate_secrets", stdout=out)
    text = out.getvalue()
    for key in ("SECRET_KEY=", "ENCRYPTION_KEY=", "STORAGE_ACCESS_KEY=",
                "STORAGE_SECRET_KEY=", "POSTGRES_PASSWORD="):
        assert key in text
    # não pode emitir os valores fracos conhecidos
    assert "wc-encr1pt10n-k3y-ch4ng3-m3-2026" not in text
    assert "wc-s3cr3t-k3y-ch4ng3-m3-1n-pr0duct10n-2026" not in text


def test_flags_weak_secret_key_as_error_in_production(settings):
    settings.DEBUG = False
    settings.SECRET_KEY = "wc-s3cr3t-k3y-ch4ng3-m3-1n-pr0duct10n-2026"

    issues = check_weak_default_secrets(None)

    assert any(i.id == "security.E001" for i in issues)


def test_flags_weak_encryption_key(settings):
    settings.DEBUG = False
    settings.ENCRYPTION_KEY = "wc-encr1pt10n-k3y-ch4ng3-m3-2026"

    issues = check_weak_default_secrets(None)

    assert any("ENCRYPTION_KEY" in i.msg for i in issues)


def test_weak_values_are_warnings_in_debug(settings):
    settings.DEBUG = True
    settings.SECRET_KEY = "wc-s3cr3t-k3y-ch4ng3-m3-1n-pr0duct10n-2026"

    issues = check_weak_default_secrets(None)

    assert issues and all(i.id == "security.W001" for i in issues)


def test_weak_minio_keys_only_warn_in_production(settings):
    # infra (MinIO/DB) exige rotacao de volume -> nao pode bloquear o deploy
    settings.DEBUG = False
    settings.AWS_ACCESS_KEY_ID = "wc-minio-access-2026"

    issues = check_weak_default_secrets(None)

    assert issues and all(i.id == "security.W002" for i in issues)


def test_passes_with_strong_values(settings):
    settings.DEBUG = False
    settings.SECRET_KEY = "uma-chave-bem-forte-e-aleatoria-xyz"
    settings.ENCRYPTION_KEY = "outra-chave-forte-abc"
    settings.AWS_ACCESS_KEY_ID = "acesso-forte"
    settings.AWS_SECRET_ACCESS_KEY = "segredo-forte"

    assert check_weak_default_secrets(None) == []
