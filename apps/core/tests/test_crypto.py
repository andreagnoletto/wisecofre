import pytest

from apps.core.crypto import decrypt_str, encrypt_str


def test_encrypt_then_decrypt_roundtrip():
    assert decrypt_str(encrypt_str("s3cr3t")) == "s3cr3t"


def test_ciphertext_is_prefixed_and_hides_plaintext():
    token = encrypt_str("minha-senha")
    assert token.startswith("fernet:")
    assert "minha-senha" not in token


def test_decrypt_passes_through_legacy_plaintext():
    # valores gravados antes da cifragem (sem prefixo) devem voltar como estão
    assert decrypt_str("valor-legado-em-texto-puro") == "valor-legado-em-texto-puro"


def test_encrypt_is_nondeterministic():
    # Fernet inclui IV/timestamp -> dois ciphertexts diferentes para o mesmo texto
    assert encrypt_str("abc") != encrypt_str("abc")


def test_empty_string_roundtrip():
    assert decrypt_str(encrypt_str("")) == ""


def test_decrypt_none_returns_none():
    assert decrypt_str(None) is None
