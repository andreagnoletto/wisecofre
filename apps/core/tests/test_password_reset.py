import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="u", email="user@x.io", password="old-pass-123", first_name="U",
    )


def test_login_page_shows_reset_link(db):
    resp = Client().get(reverse("login"))
    assert resp.status_code == 200
    assert reverse("password_reset") in resp.content.decode()


def test_reset_request_get_renders(db):
    resp = Client().get(reverse("password_reset"))
    assert resp.status_code == 200


def test_reset_request_sends_email_for_existing_user(user, monkeypatch):
    import apps.core.views_web as vw
    calls = []
    monkeypatch.setattr(vw, "_send_smtp", lambda *a, **k: calls.append(a))

    resp = Client().post(reverse("password_reset"), {"email": user.email})

    assert resp.status_code == 302
    assert resp.url == reverse("password_reset_done")
    assert len(calls) == 1
    # o e-mail vai para o endereço do usuário e contém um link /reset/
    assert calls[0][0] == user.email
    assert "/reset/" in calls[0][2]


def test_reset_request_generic_for_unknown_email(db, monkeypatch):
    import apps.core.views_web as vw
    calls = []
    monkeypatch.setattr(vw, "_send_smtp", lambda *a, **k: calls.append(a))

    resp = Client().post(reverse("password_reset"), {"email": "ghost@x.io"})

    assert resp.status_code == 302
    assert resp.url == reverse("password_reset_done")
    assert calls == []  # não envia nada para e-mail inexistente


def test_confirm_link_lets_user_set_new_password(user):
    """Loop completo: o link do e-mail leva ao formulário e define a nova senha."""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    client = Client()

    # 1) o link redireciona para o formulário de nova senha (padrão do Django)
    resp = client.get(f"/reset/{uid}/{token}/")
    assert resp.status_code == 302
    form_url = resp.url
    assert client.get(form_url).status_code == 200

    # 2) define a nova senha
    resp = client.post(form_url, {
        "new_password1": "BrandNew-Pass-9",
        "new_password2": "BrandNew-Pass-9",
    })
    assert resp.status_code == 302

    user.refresh_from_db()
    assert user.check_password("BrandNew-Pass-9")


def test_reset_request_smtp_failure_still_generic(user, monkeypatch):
    import apps.core.views_web as vw

    def boom(*a, **k):
        raise ValueError("SMTP down")

    monkeypatch.setattr(vw, "_send_smtp", boom)

    resp = Client().post(reverse("password_reset"), {"email": user.email})

    # falha de SMTP não pode vazar existência do e-mail: mesma resposta genérica
    assert resp.status_code == 302
    assert resp.url == reverse("password_reset_done")
