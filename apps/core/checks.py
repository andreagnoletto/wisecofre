"""Verificações de segurança de deploy: detecta segredos com valores padrão fracos.

Em produção (DEBUG=False) os defaults conhecidos viram ERRO (bloqueiam
`manage.py check`, e portanto migrate/collectstatic no entrypoint), forçando a
definição de valores fortes via ambiente. Em DEBUG são apenas avisos.
"""
from django.conf import settings
from django.core.checks import Error, Warning, register

# Segredos de aplicação: trocam-se só via env → BLOQUEIAM em produção.
_WEAK_BLOCKING = {
    "SECRET_KEY": "wc-s3cr3t-k3y-ch4ng3-m3-1n-pr0duct10n-2026",
    "ENCRYPTION_KEY": "wc-encr1pt10n-k3y-ch4ng3-m3-2026",
}
# Credenciais de infra (DB/MinIO): exigem rotação de volume → apenas AVISAM,
# para não derrubar deploys de instalações já existentes.
_WEAK_WARN = {
    "AWS_ACCESS_KEY_ID": "wc-minio-access-2026",
    "AWS_SECRET_ACCESS_KEY": "wc-minio-secret-key-muito-longa-2026",
}
_WEAK_DB_PASSWORD = "wc-db-p4ss-2026"

_HINT = "Gere valores fortes (python manage.py generate_secrets) e defina via variáveis de ambiente."


@register("security")
def check_weak_default_secrets(app_configs, **kwargs):
    issues = []

    for name, weak in _WEAK_BLOCKING.items():
        if getattr(settings, name, None) == weak:
            msg = f"{name} está usando o valor padrão inseguro do repositório."
            if settings.DEBUG:
                issues.append(Warning(msg, hint=_HINT, id="security.W001"))
            else:
                issues.append(Error(msg, hint=_HINT, id="security.E001"))

    warn_names = [
        name for name, weak in _WEAK_WARN.items()
        if getattr(settings, name, None) == weak
    ]
    db = (settings.DATABASES or {}).get("default", {})
    if (db.get("PASSWORD") or "") == _WEAK_DB_PASSWORD:
        warn_names.append("DATABASE (senha do Postgres)")
    for name in warn_names:
        issues.append(Warning(
            f"{name} está com o valor padrão inseguro (exige rotação manual do volume DB/MinIO).",
            hint=_HINT, id="security.W002",
        ))

    return issues
