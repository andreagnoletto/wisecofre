"""Cifra em repouso as linhas de Secret/SecretHistory que ainda estão em texto puro.

Idempotente: ler uma linha já cifrada devolve o texto claro (via EncryptedTextField)
e salvá-la re-cifra o mesmo valor. Valores legados sem prefixo são cifrados na
primeira execução. Reverso é no-op (não desfazemos a cifragem)."""
from django.conf import settings
from django.db import migrations


def encrypt_existing(apps, schema_editor):
    Secret = apps.get_model("resources", "Secret")
    SecretHistory = apps.get_model("resources", "SecretHistory")

    # Proteção contra lockout: se há segredos para cifrar mas nenhuma
    # ENCRYPTION_KEY explícita, ABORTA (em vez de cifrar com o fallback SECRET_KEY,
    # o que causaria perda de acesso ao trocar a chave depois). Bancos vazios
    # (ex.: testes/instalação nova) passam normalmente.
    has_data = Secret.objects.exists() or SecretHistory.objects.exists()
    if has_data and not getattr(settings, "ENCRYPTION_KEY", ""):
        raise RuntimeError(
            "ENCRYPTION_KEY não configurada, mas existem segredos a cifrar. "
            "Defina uma ENCRYPTION_KEY forte e PERMANENTE (e faça backup) antes de "
            "migrar — ver DEPLOY.md. Abortando para não cifrar com uma chave "
            "temporária e causar perda de acesso."
        )

    for row in Secret.objects.all().iterator():
        row.save(update_fields=["data"])
    for row in SecretHistory.objects.all().iterator():
        row.save(update_fields=["data"])


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0002_alter_secret_data_alter_secrethistory_data"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
