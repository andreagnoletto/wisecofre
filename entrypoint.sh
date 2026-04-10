#!/bin/bash
set -e

echo "=== Wisecofre entrypoint ==="

echo "Aguardando banco de dados..."
until python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()
from django.db import connection
connection.ensure_connection()
print('DB ready')
"; do
  echo "  DB nao disponivel, tentando novamente em 3s..."
  sleep 3
done

echo "Executando migrations..."
python manage.py migrate --noinput

echo "Criando tabela de cache..."
python manage.py createcachetable --database default 2>/dev/null || true

echo "Coletando arquivos estaticos..."
python manage.py collectstatic --noinput

echo "Iniciando servidor..."
exec "$@"
