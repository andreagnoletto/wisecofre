# Deploy Wisecofre no Coolify

## Arquitetura

```
Internet -> Coolify/Traefik (TLS) -> web:8003 (Gunicorn/Django)
                                        |
                              +---------+---------+
                              |                   |
                             db                 minio
                          (PostgreSQL)        (Storage S3)
                              |
                          minio-init
                        (cria bucket, roda 1x)
```

Tudo roda num unico `docker-compose.yml`:

| Servico | Funcao |
|---|---|
| **web** | Django/Gunicorn (porta 8003) |
| **db** | PostgreSQL 16 |
| **minio** | Object storage S3-compatible |
| **minio-init** | Cria bucket (roda uma vez e para) |

## Passo a passo no Coolify

### 1. Criar recurso

- Tipo: **Docker Compose**
- Repositorio: `https://github.com/andreagnoletto/wisecofre`
- Branch: `main`
- Docker Compose Location: `docker-compose.yml`

### 2. Configurar dominio

Na configuracao do recurso no Coolify:

| Servico | Dominio | Porta |
|---|---|---|
| **web** | `https://cofre.wisedoc.com.br` | `8003` |
| demais | *(vazio)* | - |

> O Traefik do Coolify faz TLS + reverse proxy para o `web:8003`.

### 3. Variaveis de ambiente

Use **Bulk Edit** no Coolify e cole o conteudo de `.env.coolify` (ja incluso no repo).

Variaveis criticas para trocar antes do primeiro deploy:

| Variavel | Acao |
|---|---|
| `SECRET_KEY` | Gerar: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `POSTGRES_PASSWORD` | Escolher senha forte |
| `DATABASE_URL` | Atualizar com a senha do `POSTGRES_PASSWORD` |
| `STORAGE_ACCESS_KEY` | Escolher credencial MinIO |
| `STORAGE_SECRET_KEY` | Escolher credencial MinIO (longa) |
| `ENCRYPTION_KEY` | Gerar: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Variaveis de seguranca (defaults corretos para producao via HTTPS):

| Variavel | Valor producao | Valor local |
|---|---|---|
| `SESSION_COOKIE_SECURE` | `True` (default) | `False` |
| `CSRF_COOKIE_SECURE` | `True` (default) | `False` |
| `SECURE_SSL_REDIRECT` | `False` (Traefik redireciona) | `False` |

> **IMPORTANTE:** `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` devem ser `True` em producao (HTTPS).
> No `docker-compose.yml` o default e `False` para permitir testes locais via HTTP.
> No Coolify, defina `SESSION_COOKIE_SECURE=True` e `CSRF_COOKIE_SECURE=True`.

### 4. DNS

- Apontar `cofre.wisedoc.com.br` (A record) para o IP do servidor Coolify
- SSL automatico via Let's Encrypt (habilitado no Coolify)

### 5. Deploy

Clicar em **Deploy** no Coolify. O processo:

1. Builda a imagem Docker
2. Sobe db, minio (aguarda healthchecks)
3. `minio-init` cria o bucket
4. `entrypoint.sh` do web: aguarda DB, roda migrations, cria cache table, collectstatic
5. Gunicorn inicia na porta 8003

### 6. Criar usuario admin

Apos o primeiro deploy, no terminal do Coolify ou via SSH:

```bash
# Via Coolify web terminal (clique no container web > Terminal)
python manage.py createsuperuser

# Ou via SSH no servidor
docker exec -it $(docker ps -qf "name=web") python manage.py createsuperuser
```

### 7. Deploy automatico

Se o webhook estiver configurado no Coolify, cada `git push` no branch `main` dispara um redeploy automatico.

## Testes E2E contra Coolify

Apos o deploy, rode os testes da sua maquina local:

```bash
# PowerShell
$env:E2E_BASE_URL = "https://cofre.wisedoc.com.br"
uv run python -m pytest tests/test_e2e.py -v --override-ini="django_find_project=false"
```

> Os 6 testes de seguranca que acessam o DB diretamente serao **skipped** sem `E2E_DATABASE_URL`.
> Os outros 81 testes rodam normalmente via HTTP/browser.

## Notas

- `SECURE_SSL_REDIRECT=False` — Traefik do Coolify ja redireciona HTTP->HTTPS
- `MINIO_ENDPOINT=minio:9000` — comunicacao interna Docker (sem HTTPS)
- O bucket e criado automaticamente pelo servico `minio-init`
- Migrations, cache table e collectstatic rodam automaticamente no `entrypoint.sh`
- Whitenoise serve arquivos estaticos (nao precisa nginx)
- Nao usa Redis nem Celery — cache via Django DatabaseCache, tarefas sincronas
- A porta do DB (`5433` no host) e exposta apenas para testes E2E locais
- `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` sao `False` no compose (HTTP local) — defina `True` no Coolify (HTTPS)
