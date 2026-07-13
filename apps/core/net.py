"""Resolução do IP real do cliente atrás de proxy reverso (Coolify/Traefik).

O X-Forwarded-For pode ser forjado pelo cliente. Com N proxies confiáveis
(TRUSTED_PROXY_COUNT), a entrada adicionada pelo proxy mais externo confiável é a
N-ésima a partir da direita — as posições à esquerda dela podem ser spoof e são
ignoradas. Para o Coolify (1 proxy Traefik), o IP real é o mais à direita.
"""
import ipaddress

from django.conf import settings


def client_ip(request):
    n = int(getattr(settings, "TRUSTED_PROXY_COUNT", 1) or 1)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if len(parts) >= n:
        ip = parts[-n]
    elif parts:
        ip = parts[0]
    else:
        ip = request.META.get("REMOTE_ADDR", "") or ""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        ip = request.META.get("REMOTE_ADDR", "") or "0.0.0.0"
    return ip


def mfa_target_key(group, request):
    """Chave de rate limit do MFA: limita por usuário-alvo (mfa_user_id na sessão),
    independente do IP — evita brute-force de TOTP trocando de IP. Cai para o IP se
    não houver sessão de MFA."""
    return str(request.session.get("mfa_user_id") or "") or client_ip(request)
