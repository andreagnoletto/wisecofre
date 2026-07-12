"""Gera uma ENCRYPTION_KEY forte para a cifragem em repouso.

    python manage.py generate_encryption_key

Copie o valor para a variável de ambiente ENCRYPTION_KEY e faça BACKUP seguro:
perder a chave significa perder o acesso a todos os segredos cifrados.
"""
from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Gera uma ENCRYPTION_KEY forte para cifragem em repouso."

    def handle(self, *args, **options):
        key = Fernet.generate_key().decode()
        self.stdout.write(self.style.SUCCESS(key))
        self.stdout.write(
            "\nDefina em ENCRYPTION_KEY e faça BACKUP seguro. "
            "Perder a chave = perder todos os segredos cifrados."
        )
