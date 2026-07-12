"""Gera um conjunto de segredos fortes para uma instalação nova.

    python manage.py generate_secrets

Imprime valores prontos para colar no .env / Coolify. Não escreve arquivos nem
grava nada — o operador copia para um local seguro.
"""
import secrets

from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = "Gera segredos fortes (SECRET_KEY, ENCRYPTION_KEY, credenciais DB/MinIO)."

    def handle(self, *args, **options):
        lines = [
            f"SECRET_KEY={get_random_secret_key()}",
            f"ENCRYPTION_KEY={Fernet.generate_key().decode()}",
            f"STORAGE_ACCESS_KEY={secrets.token_urlsafe(24)}",
            f"STORAGE_SECRET_KEY={secrets.token_urlsafe(48)}",
            f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}",
        ]
        self.stdout.write("\n".join(lines))
        self.stdout.write(self.style.WARNING(
            "\n# Cole no .env/Coolify. Atualize DATABASE_URL com o POSTGRES_PASSWORD acima."
            "\n# ENCRYPTION_KEY e PERMANENTE: faca backup (perde-la = perder os segredos cifrados)."
            "\n# Em instalacao existente, DB/MinIO exigem rotacao manual (nao basta a env)."
        ))
