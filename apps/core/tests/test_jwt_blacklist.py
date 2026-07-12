from rest_framework.test import APIClient

from apps.accounts.models import User


def test_refresh_is_rejected_after_logout_blacklist(db):
    User.objects.create_user(username="j", email="j@x.io", password="pass-123456")
    client = APIClient()

    tokens = client.post(
        "/api/v1/auth/token/", {"email": "j@x.io", "password": "pass-123456"}, format="json"
    ).json()
    refresh = tokens["refresh"]

    # logout coloca o refresh na blacklist
    r = client.post("/api/v1/auth/logout/", {"refresh": refresh}, format="json")
    assert r.status_code in (200, 204)

    # tentar renovar com o refresh revogado agora falha
    r2 = client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json")
    assert r2.status_code == 401
