#!/bin/bash
set -e

echo "Aguardando banco de dados..."
until python -c "
import django; django.setup()
from django.db import connection
connection.ensure_connection()
print('DB ready')
" 2>/dev/null; do
  sleep 2
done

echo "Aguardando MinIO..."
until curl -sf http://${MINIO_ENDPOINT:-minio:9000}/minio/health/live 2>/dev/null; do
  sleep 2
done

echo "Criando bucket MinIO se não existir..."
python -c "
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os

client = boto3.client(
    's3',
    endpoint_url=f\"http://{os.environ.get('MINIO_ENDPOINT', 'minio:9000')}\",
    aws_access_key_id=os.environ.get('MINIO_ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('MINIO_SECRET_KEY'),
    config=Config(signature_version='s3v4'),
)
bucket = os.environ.get('MINIO_BUCKET_NAME', 'wisecofre-files')
try:
    client.head_bucket(Bucket=bucket)
    print(f'Bucket {bucket} já existe.')
except ClientError:
    client.create_bucket(Bucket=bucket)
    print(f'Bucket {bucket} criado.')
"
echo "MinIO pronto."

echo "Executando migrations..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "Iniciando servidor..."
exec "$@"
