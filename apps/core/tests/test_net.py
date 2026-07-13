from django.test import RequestFactory

from apps.core.net import client_ip


def test_client_ip_uses_trusted_proxy_entry_rightmost(db, settings):
    # 1 proxy confiável: o IP real é o mais à direita (o que o proxy adicionou);
    # a entrada à esquerda pode ser spoof do cliente e é ignorada.
    settings.TRUSTED_PROXY_COUNT = 1
    req = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9", REMOTE_ADDR="10.0.0.1"
    )
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_falls_back_to_remote_addr_without_xff(db):
    req = RequestFactory().get("/", REMOTE_ADDR="192.0.2.5")
    assert client_ip(req) == "192.0.2.5"


def test_client_ip_invalid_value_falls_back(db, settings):
    settings.TRUSTED_PROXY_COUNT = 1
    req = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="not-an-ip", REMOTE_ADDR="192.0.2.9"
    )
    assert client_ip(req) == "192.0.2.9"


def test_client_ip_two_trusted_proxies(db, settings):
    settings.TRUSTED_PROXY_COUNT = 2
    # cliente, proxy externo, proxy interno -> real = 2º da direita
    req = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="203.0.113.9, 70.0.0.1, 10.0.0.2"
    )
    assert client_ip(req) == "70.0.0.1"
