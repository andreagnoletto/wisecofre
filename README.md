# Wisecofre

Gerenciador de senhas, arquivos e segredos com criptografia — alternativa self-hosted ao Passbolt.

## Features

- Senhas com criptografia e compartilhamento entre usuarios
- Upload de arquivos criptografados via MinIO (S3)
- Pastas e subpastas para organizacao
- Grupos com controle de membros (admin/membro)
- MFA com TOTP (Google Authenticator, Microsoft Authenticator, etc.)
- Auditoria automatica de todas as acoes (middleware)
- Painel de configuracoes dinamico (seguranca, storage, SSO)
- Camada de servicos com autorizacao centralizada
- 87 testes E2E com Playwright

## Stack

| Componente | Tecnologia |
|---|---|
| Backend | Django 6, DRF |
| Frontend | Django Templates, Alpine.js, Bootstrap 5.3 |
| Database | PostgreSQL 16 |
| Cache/Broker | Redis 7 |
| Storage | MinIO (S3-compatible) |
| Tasks | Celery + Celery Beat |
| Auth | Session + JWT, TOTP MFA |
| Deploy | Docker Compose, Coolify |

## Dev Local

```bash
# 1. Subir infra
docker compose up -d

# 2. Copiar .env
cp .env.example .env

# 3. Instalar dependencias
uv sync

# 4. Migrations e servidor
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Acesse `http://localhost:8000`

## Testes

```bash
# Subir infra + servidor Django antes
uv run python -m pytest tests/test_e2e.py -v
```

## Deploy (Coolify)

Veja [DEPLOY.md](DEPLOY.md) para instrucoes completas.

## Estrutura

```
wisecofre/
├── apps/
│   ├── accounts/     # Usuario, perfil
│   ├── audit/        # Logs, middleware
│   ├── core/         # Services, views web
│   ├── files/        # Upload/download criptografado
│   ├── folders/      # Pastas e subpastas
│   ├── groups/       # Grupos e membros
│   ├── mfa/          # TOTP, backup codes
│   ├── resources/    # Senhas, secrets, tags
│   └── sharing/      # Permissoes, compartilhamento
├── config/           # Settings, URLs, WSGI
├── Dockerfile        # Imagem Docker
├── entrypoint.sh     # Entrypoint do container
├── templates/        # Django templates
├── tests/            # E2E Playwright
├── docker-compose.yml       # Dev local (infra)
└── docker-compose.prod.yml  # Producao (Coolify)
```
