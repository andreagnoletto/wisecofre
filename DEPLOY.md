# Deploy Wisecofre no Coolify

## Arquitetura de Producao

```
Internet -> Coolify Traefik (TLS) -> web:8000 (Gunicorn/Django)
                                        |
                              +---------+---------+
                              |         |         |
                             db      redis     minio
                          (Postgres) (Cache)  (Storage)
                              |
                     +--------+--------+
                     |                 |
                   celery         celery-beat
                  (Worker)       (Scheduler)
```

Servicos no `docker-compose.prod.yml`:

| Servico | Funcao |
|---|---|
| **web** | Django/Gunicorn (porta 8000) |
| **db** | PostgreSQL 16 |
| **redis** | Cache + Celery broker |
| **celery** | Worker async |
| **celery-beat** | Scheduler de tarefas |
| **minio** | Object storage S3-compatible |
| **minio-init** | Cria bucket (roda uma vez) |

## Passo a passo no Coolify

### 1. Criar recurso

- Tipo: **Docker Compose**
- Repositorio: `https://github.com/andreagnoletto/wisecofre`
- Branch: `main`
- Docker Compose Location: `docker-compose.prod.yml`

### 2. Configurar dominio

Na configuracao do recurso no Coolify:

| Servico | Dominio | Porta |
|---|---|---|
| **web** | `https://cofre.wisedoc.com.br` | `8000` |
| demais | *(vazio)* | - |

> O Traefik do Coolify faz TLS + reverse proxy para o `web:8000`.

### 3. Variaveis de ambiente

Configurar no Coolify (Environment Variables):

```env
# Django
SECRET_KEY=<gerar: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=cofre.wisedoc.com.br

# Database (hosts internos Docker)
DATABASE_URL=postgresql://wisecofre:SENHA_SEGURA_DB@db:5432/wisecofre
POSTGRES_DB=wisecofre
POSTGRES_USER=wisecofre
POSTGRES_PASSWORD=SENHA_SEGURA_DB

# Redis
REDIS_URL=redis://:SENHA_SEGURA_REDIS@redis:6379/0
REDIS_PASSWORD=SENHA_SEGURA_REDIS
CELERY_BROKER_URL=redis://:SENHA_SEGURA_REDIS@redis:6379/1

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=GERAR_ACCESS_KEY
MINIO_SECRET_KEY=GERAR_SECRET_KEY_LONGA
MINIO_BUCKET_NAME=wisecofre-files
MINIO_USE_HTTPS=False

# App
APP_BASE_URL=https://cofre.wisedoc.com.br
APP_NAME=Wisecofre

# CSRF / CORS
CSRF_TRUSTED_ORIGINS=https://cofre.wisedoc.com.br
CORS_ALLOWED_ORIGINS=https://cofre.wisedoc.com.br

# SSL (Coolify/Traefik gerencia)
SECURE_SSL_REDIRECT=False

# Email (ajustar para SMTP real)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seuservidor.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@cofre.wisedoc.com.br

# Seguranca
ENCRYPTION_KEY=<gerar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=30
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Limites
FILE_MAX_SIZE_BYTES=10485760
```

### 4. DNS

- Apontar `cofre.wisedoc.com.br` (A record) para o IP do servidor Coolify
- SSL automatico via Let's Encrypt (habilitado no Coolify)

### 5. Deploy

Clicar em **Deploy** no Coolify. O processo:

1. Builda a imagem Docker
2. Sobe db, redis, minio (aguarda healthchecks)
3. `minio-init` cria o bucket
4. `entrypoint.sh` do web: aguarda DB, roda migrations, collectstatic
5. Gunicorn inicia na porta 8000
6. Celery e celery-beat iniciam

### 6. Criar usuario admin

Apos o primeiro deploy, executar no terminal do Coolify (ou SSH no servidor):

```bash
docker exec -it <container-web> python manage.py createsuperuser
```

### Notas

- `SECURE_SSL_REDIRECT=False` — Traefik do Coolify ja redireciona HTTP->HTTPS
- `MINIO_ENDPOINT=minio:9000` — comunicacao interna Docker (sem HTTPS)
- O bucket e criado automaticamente pelo servico `minio-init`
- Migrations e collectstatic rodam automaticamente no entrypoint
- Whitenoise serve arquivos estaticos (nao precisa nginx)

## Dev Local

```bash
# Subir infra (PostgreSQL + Redis + MinIO)
docker compose up -d

# Instalar dependencias e rodar Django
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

MinIO console: `http://localhost:9001` (user: `wisecofre-access-key`)
