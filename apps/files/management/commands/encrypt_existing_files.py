"""Cifra em repouso os arquivos legados (gravados antes da cifragem no servidor).

Percorre os FileResource cujo encryption_version ainda não é 'fernet-v1', lê os
bytes do storage, cifra, regrava e marca. Idempotente (pula os já cifrados).

RODAR EM JANELA DE MANUTENÇÃO E COM BACKUP DO STORAGE.

Uso:
  python manage.py encrypt_existing_files --dry-run
  python manage.py encrypt_existing_files
"""
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.core.crypto import encrypt_bytes
from apps.files.models import FileResource


class Command(BaseCommand):
    help = "Cifra em repouso os arquivos legados (encryption_version != fernet-v1)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Só mostra o que faria.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        fernet = FileResource.EncryptionVersion.FERNET_V1
        qs = FileResource.objects.exclude(encryption_version=fernet)
        total = qs.count()
        self.stdout.write(f"{total} arquivo(s) legado(s) a cifrar." + (" [DRY-RUN]" if dry else ""))

        done = skipped = 0
        for fr in qs.iterator():
            key = fr.storage_key
            if not key or not default_storage.exists(key):
                self.stderr.write(f"  ! sem storage: {fr.pk} ({key}) — pulado")
                skipped += 1
                continue
            if dry:
                self.stdout.write(f"  ~ cifraria {fr.pk} ({key})")
                done += 1
                continue
            with default_storage.open(key, "rb") as f:
                plaintext = f.read()
            encrypted = encrypt_bytes(plaintext)
            default_storage.delete(key)
            new_key = default_storage.save(key, ContentFile(encrypted))
            fr.storage_key = new_key
            fr.encryption_version = fernet
            fr.save(update_fields=["storage_key", "encryption_version", "modified_at"])
            done += 1

        self.stdout.write(self.style.SUCCESS(f"Concluído: {done} cifrado(s), {skipped} pulado(s)."))
