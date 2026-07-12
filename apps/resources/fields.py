from django.db import models

from apps.core.crypto import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
    """TextField que cifra o valor em repouso de forma transparente.

    Grava cifrado (prefixo ``fernet:``) e devolve o texto claro ao ler. Valores
    legados sem prefixo são devolvidos como estão (ver apps/core/crypto.py)."""

    def from_db_value(self, value, expression, connection):
        return decrypt_str(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None
        return encrypt_str(value)
