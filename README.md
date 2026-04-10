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
| Cache | Django DatabaseCache |
| Storage | MinIO (S3-compatible) |
| Auth | Session + JWT, TOTP MFA |
| Deploy | Docker Compose, Coolify |

## Dev Local (Docker)

Tudo roda num unico `docker-compose.yml` (web, db, minio):

```bash
docker compose up -d --build
```

Acesse `http://localhost:8003`

Criar usuario admin:

```bash
docker compose exec web python manage.py createsuperuser
```

## Dev Local (sem Docker)

```bash
# 1. Subir infra (PostgreSQL + MinIO)
docker compose up -d db minio minio-init

# 2. Copiar .env e ajustar
cp .env.example .env

# 3. Instalar dependencias
uv sync

# 4. Migrations e servidor
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver 8003
```

Acesse `http://localhost:8003`

## Testes E2E

Os 87 testes E2E rodam com Playwright contra a aplicacao rodando (Docker ou Coolify).

> **IMPORTANTE:** Os testes E2E rodam na sua **maquina local** (Windows/PowerShell).
> O Playwright abre um browser local que acessa a aplicacao remotamente.
> Nao rode esses comandos dentro do Coolify ou de um servidor Linux.

### Contra Docker local

```powershell
# 1. Garantir que o Docker esta rodando
docker compose up -d --build

# 2. Instalar dependencias de teste (apenas na primeira vez)
uv pip install pytest playwright pytest-playwright psycopg pyotp requests
uv run python -m playwright install chromium

# 3. Setar variaveis e rodar testes
$env:E2E_BASE_URL = "http://localhost:8003"
$env:E2E_DATABASE_URL = "postgresql://wisecofre:wc-db-p4ss-2026@localhost:5433/wisecofre"
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
$env:SECRET_KEY = "test-key"
uv run python -m pytest tests/test_e2e.py -v --override-ini="django_find_project=false"
```

> Com `E2E_DATABASE_URL` definido, os testes criam usuarios temporarios dedicados
> (`testadm-xxx@wisecofre.io`, `testusr-xxx@wisecofre.io`) no inicio e removem no final.
> O admin real da aplicacao **nunca e tocado**.

### Contra Coolify (producao)

Rode no PowerShell da sua maquina local (nao no servidor).
E necessario expor a porta do DB ou criar um tunnel SSH para que `E2E_DATABASE_URL` funcione:

```powershell
$env:E2E_BASE_URL = "https://cofre.wisedoc.com.br"
$env:E2E_DATABASE_URL = "postgresql://wisecofre:SENHA@IP_SERVIDOR:5433/wisecofre"
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
$env:SECRET_KEY = "test-key"
uv run python -m pytest tests/test_e2e.py -v --override-ini="django_find_project=false"
```

> Sem `E2E_DATABASE_URL` os testes usam credenciais fixas (`admin@wisecofre.io` / `admin123admin123`)
> e os 6 testes de seguranca com acesso direto ao DB serao **skipped**.
> Com `E2E_DATABASE_URL` os testes criam/destroem usuarios dedicados automaticamente.

### Variaveis de ambiente dos testes

| Variavel | Default | Descricao |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:8003` | URL da aplicacao |
| `E2E_DATABASE_URL` | *(vazio)* | Conexao direta ao DB — habilita usuarios dedicados e testes de seguranca |
| `DJANGO_SETTINGS_MODULE` | `config.settings.test` | Settings do Django (necessario para pytest-django) |
| `SECRET_KEY` | *(obrigatorio)* | Qualquer valor para pytest-django carregar |

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
├── templates/        # Django templates
├── tests/            # E2E Playwright
├── Dockerfile        # Imagem Docker
├── entrypoint.sh     # Entrypoint do container
└── docker-compose.yml  # Unico compose (local + Coolify)
```
