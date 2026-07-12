"""
Cifragem em repouso (Fernet / AES-128-CBC + HMAC).

Protege segredos e conteúdo de arquivos contra vazamento do banco/backup/storage.
NÃO é E2E: o servidor consegue decifrar (a chave vive no ambiente). É a primeira
camada — muito melhor que texto puro.

A chave vem de ``settings.ENCRYPTION_KEY``. Como a chave pode ser uma passphrase
arbitrária, derivamos uma chave Fernet válida via SHA-256. Se ``ENCRYPTION_KEY``
estiver vazia (dev/testes), caímos para ``SECRET_KEY`` com um aviso — em produção
uma chave dedicada DEVE ser configurada (ver DEPLOY.md).

Valores cifrados recebem o prefixo ``fernet:``. ``decrypt_str`` devolve valores sem
o prefixo como estão (compatibilidade com dados legados em texto puro), o que
permite migração incremental e reversível.
"""
import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger("wisecofre")

_PREFIX = "fernet:"


@lru_cache(maxsize=1)
def _fernet():
    key_material = getattr(settings, "ENCRYPTION_KEY", "") or ""
    if not key_material:
        logger.warning(
            "ENCRYPTION_KEY não configurada; usando SECRET_KEY para cifragem em "
            "repouso. Configure uma ENCRYPTION_KEY dedicada em produção."
        )
        key_material = settings.SECRET_KEY
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt_str(plaintext):
    if plaintext is None:
        return None
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_str(value):
    if value is None:
        return None
    if not is_encrypted(value):
        return value  # legado em texto puro
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.error("Falha ao decifrar valor em repouso (InvalidToken).")
        raise


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)
