import sys

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verifica a saúde dos serviços: banco de dados e MinIO"

    def handle(self, *args, **options):
        ok = True

        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS("[OK]  Database"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"[FAIL] Database: {exc}"))
            ok = False

        try:
            from django.core.cache import cache
            cache.set("_healthcheck", "1", timeout=5)
            assert cache.get("_healthcheck") == "1"
            cache.delete("_healthcheck")
            self.stdout.write(self.style.SUCCESS("[OK]  Cache"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"[FAIL] Cache: {exc}"))
            ok = False

        try:
            import boto3
            from botocore.config import Config
            from django.conf import settings

            client = boto3.client(
                "s3",
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )
            client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
            self.stdout.write(self.style.SUCCESS(f"[OK]  MinIO (bucket: {settings.AWS_STORAGE_BUCKET_NAME})"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"[FAIL] MinIO: {exc}"))
            ok = False

        self.stdout.write("")
        if ok:
            self.stdout.write(self.style.SUCCESS("Todos os serviços estão saudáveis."))
        else:
            self.stdout.write(self.style.ERROR("Um ou mais serviços com problema."))
            sys.exit(1)
