# Deploy Wisecofre no Coolify

## Arquitetura

O deploy usa `docker-compose.prod.yml` que sobe todos os servicos:

- **nginx** - Reverse proxy (porta 80)
- **web** - Django/Gunicorn
- **db** - PostgreSQL 16
- **redis** - Redis 7
- **celery** - Worker Celery
- **celery-beat** - Scheduler Celery
- **minio** - Object storage (S3-compatible)

## Configuracao no Coolify

### 1. Criar novo recurso

- Tipo: **Docker Compose**
- Repositorio: apontar para o repo Git
- Docker Compose Location: `docker-compose.prod.yml`
- Build Context: raiz do repositorio (`.`)

### 2. Variaveis de ambiente

Configurar as seguintes variaveis no Coolify:

```env
# Django
SECRET_KEY=gerar-com-python-c-"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=wisecofre.wisedoc.com.br

# Database (interno entre containers)
DATABASE_URL=postgresql://wisecofre:SENHA_SEGURA_DB@db:5432/wisecofre
POSTGRES_DB=wisecofre
POSTGRES_USER=wisecofre
POSTGRES_PASSWORD=SENHA_SEGURA_DB

# Redis (interno entre containers)
REDIS_URL=redis://:SENHA_SEGURA_REDIS@redis:6379/0
REDIS_PASSWORD=SENHA_SEGURA_REDIS
CELERY_BROKER_URL=redis://:SENHA_SEGURA_REDIS@redis:6379/1

# MinIO (interno entre containers)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=GERAR_ACCESS_KEY_SEGURA
MINIO_SECRET_KEY=GERAR_SECRET_KEY_SEGURA_LONGA
MINIO_BUCKET_NAME=wisecofre-files
MINIO_USE_HTTPS=False

# App
APP_BASE_URL=https://wisecofre.wisedoc.com.br
APP_NAME=Wisecofre

# CSRF / CORS
CSRF_TRUSTED_ORIGINS=https://wisecofre.wisedoc.com.br
CORS_ALLOWED_ORIGINS=https://wisecofre.wisedoc.com.br

# SSL (Coolify gerencia via Traefik/Caddy)
SECURE_SSL_REDIRECT=False

# Email (configurar SMTP real)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seuservidor.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@wisecofre.wisedoc.com.br

# Seguranca
ENCRYPTION_KEY=gerar-com-python-c-"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=30
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Limites
FILE_MAX_SIZE_BYTES=10485760
MINIO_PRESIGNED_URL_EXPIRY_SECONDS=60
MINIO_UPLOAD_URL_EXPIRY_SECONDS=900
```

### 3. Dominio

- Configurar dominio `wisecofre.wisedoc.com.br` no Coolify
- Apontar DNS (A record) para o IP do servidor Coolify
- Habilitar SSL automatico (Let's Encrypt)
- Porta exposta: **80** (do nginx)

### 4. Notas importantes

- `SECURE_SSL_REDIRECT=False` porque o Coolify/Traefik ja faz o redirect HTTPS
- `MINIO_ENDPOINT=minio:9000` usa o nome do servico Docker (interno)
- `MINIO_USE_HTTPS=False` porque a comunicacao MinIO e interna entre containers
- O bucket e criado automaticamente pelo `entrypoint.sh`
- O `collectstatic` roda automaticamente no entrypoint

### 5. Criar usuario admin apos deploy

```bash
docker compose exec web python manage.py createsuperuser
```

## Dev Local

Para desenvolvimento local, use o `docker-compose.yml` da raiz (somente infra):

```bash
# Subir infra (PostgreSQL + Redis + MinIO)
docker compose up -d

# Rodar Django localmente
uv run python manage.py migrate
uv run python manage.py runserver
```

O MinIO console fica acessivel em `http://localhost:9001` (user: `wisecofre-access-key`, pass: `wisecofre-secret-key-muito-longa`).
