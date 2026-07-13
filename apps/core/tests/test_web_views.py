import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import ActionLog
from apps.files.models import FileAccessLog, FileResource, FileSecret
from apps.folders.models import Folder
from apps.groups.models import Group, GroupUser
from apps.resources.models import Resource, ResourceType, Secret, SecretHistory


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="o", email="o@x.io", password="x", first_name="O")


@pytest.fixture
def other(db):
    return User.objects.create_user(username="n", email="n@x.io", password="x", first_name="N")


def make_password(owner, data="segredo", **kw):
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    r = Resource.objects.create(name="p", resource_type=rt, created_by=owner, **kw)
    Secret.objects.create(resource=r, user=owner, data=data)
    return r


# ── #2 copy secret on demand ────────────────────────────────────────────────

def test_password_secret_returns_data_for_user_with_access(owner):
    resource = make_password(owner, data="minha-senha")
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("password_secret", args=[resource.pk]))

    assert resp.status_code == 200
    assert resp.json()["data"] == "minha-senha"


def test_password_secret_denied_without_access(owner, other):
    resource = make_password(owner, data="x")
    client = Client()
    client.force_login(other)

    resp = client.get(reverse("password_secret", args=[resource.pk]))

    assert resp.status_code == 403


# ── #6 files browsed by folder ──────────────────────────────────────────────

def make_file(owner, folder=None):
    rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    r = Resource.objects.create(name="f", resource_type=rt, created_by=owner, folder=folder)
    fr = FileResource.objects.create(
        resource=r, storage_key=f"k/{r.pk}", size_bytes=1, original_name_encrypted="f.txt",
        mime_category="document", checksum_sha256="c", upload_completed=True, created_by=owner,
    )
    FileSecret.objects.create(file_resource=fr, user=owner, session_key_encrypted="local")
    return fr


def test_file_list_root_shows_only_unfiled_files(owner):
    folder = Folder.objects.create(name="F", created_by=owner)
    filed = make_file(owner, folder=folder)
    unfiled = make_file(owner, folder=None)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("file_list"))
    pks = {f.pk for f in resp.context["files"]}

    assert unfiled.pk in pks
    assert filed.pk not in pks


def test_file_list_inside_folder_shows_its_files(owner):
    folder = Folder.objects.create(name="F", created_by=owner)
    filed = make_file(owner, folder=folder)
    unfiled = make_file(owner, folder=None)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("file_list"), {"folder": str(folder.pk)})
    pks = {f.pk for f in resp.context["files"]}

    assert filed.pk in pks
    assert unfiled.pk not in pks


# ── #5 audit captures email on anonymous login ──────────────────────────────

def test_logout_is_attributed_to_the_acting_user(owner):
    client = Client()
    client.force_login(owner)

    client.post(reverse("logout"))

    log = ActionLog.objects.filter(action="logout").order_by("-created_at").first()
    assert log is not None
    assert log.user_id == owner.pk  # nao pode ser None (o usuario acabou de deslogar)


def test_failed_login_records_attempted_email(db):
    from django.core.cache import cache
    cache.clear()
    client = Client()
    client.post(reverse("login"), {"email": "ghost@x.io", "password": "wrong"})

    log = ActionLog.objects.filter(action="login").order_by("-created_at").first()
    assert log is not None
    assert log.context.get("email") == "ghost@x.io"


def test_login_is_rate_limited_after_repeated_failures(db):
    from django.core.cache import cache
    cache.clear()
    User.objects.create_user(username="rl", email="rl@x.io", password="correct-pass-123")
    client = Client()

    last = None
    for _ in range(7):
        last = client.post(reverse("login"), {"email": "rl@x.io", "password": "errada"})

    assert "Muitas tentativas" in last.content.decode()


# ── render smoke tests (pegam erros de template) ────────────────────────────

def test_password_list_renders_with_share_modal_and_copy(owner):
    make_password(owner)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("password_list"))

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "shareModal" in body
    assert "copyPasswordSecret" in body


def test_password_create_preselects_folder(owner):
    folder = Folder.objects.create(name="F", created_by=owner)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("password_create"), {"folder": str(folder.pk)})

    assert resp.status_code == 200
    assert "selected" in resp.content.decode()


def test_files_list_renders_folders(owner):
    Folder.objects.create(name="Docs", created_by=owner)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("file_list"))

    assert resp.status_code == 200
    assert "Docs" in resp.content.decode()


def test_audit_export_neutralizes_formula_injection(db):
    admin = User.objects.create_user(
        username="ax", email="ax@x.io", password="x", role="ADMIN", is_staff=True,
    )
    ActionLog.objects.create(
        user=admin, action="=SUM(A1)", status="success", ip_address="1.1.1.1",
    )
    client = Client()
    client.force_login(admin)

    resp = client.get(reverse("audit_export_csv"))

    body = resp.content.decode()
    assert "'=SUM(A1)" in body  # célula neutralizada com aspa simples


def test_folder_with_passwords_hides_no_subfolder_empty_state(owner):
    folder = Folder.objects.create(name="F", created_by=owner)
    rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
    resource = Resource.objects.create(
        name="teste senha em grupo", resource_type=rt, created_by=owner, folder=folder,
    )
    Secret.objects.create(resource=resource, user=owner, data="x")
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("folder_detail", args=[folder.pk]))

    body = resp.content.decode()
    assert resp.status_code == 200
    assert "teste senha em grupo" in body          # a senha aparece
    assert "Nenhuma sub-pasta" not in body          # não mostra o estado-vazio confuso
    assert "Esta pasta não tem sub-pastas" not in body


def test_truly_empty_folder_shows_empty_state(owner):
    folder = Folder.objects.create(name="Vazia", created_by=owner)
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("folder_detail", args=[folder.pk]))

    assert resp.status_code == 200
    assert "Pasta vazia" in resp.content.decode()


def test_settings_page_shows_security_status(db):
    admin = User.objects.create_user(
        username="s", email="s@x.io", password="x", role="ADMIN", is_staff=True,
    )
    client = Client()
    client.force_login(admin)

    resp = client.get(reverse("admin_settings"))

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Status de Segurança" in body
    assert "Cifragem em repouso" in body


def test_audit_detail_shows_resource_name(db):
    admin = User.objects.create_user(
        username="a", email="a@x.io", password="x", role="ADMIN", is_staff=True,
    )
    resource = make_password(admin)
    ActionLog.objects.create(
        user=admin, action="password_detail", status="success", ip_address="1.1.1.1",
        context={"params": {"pk": str(resource.pk)}},
    )
    client = Client()
    client.force_login(admin)

    resp = client.get(reverse("audit_logs"))

    assert resp.status_code == 200
    # o nome do recurso aparece nos detalhes, em vez de "pk=<uuid>"
    assert resource.name in resp.content.decode()


# ── group detail lists shared resources ─────────────────────────────────────

def _make_group(owner):
    g = Group.objects.create(name="Equipe", created_by=owner)
    GroupUser.objects.create(group=g, user=owner, is_admin=True)
    return g


def test_group_detail_lists_shared_password(owner):
    group = _make_group(owner)
    resource = make_password(owner)
    client = Client()
    client.force_login(owner)
    client.post(
        reverse("password_share", args=[resource.pk]),
        {"share_type": "group", "group_id": str(group.pk), "permission": "read"},
    )

    resp = client.get(reverse("group_detail", args=[group.pk]))

    assert resp.status_code == 200
    assert len(resp.context["shared_resources"]) == 1
    assert resource.name in resp.content.decode()


def test_password_update_records_secret_history(owner):
    from apps.core.services import PasswordService

    resource = make_password(owner, data="v1")
    PasswordService.update(owner, resource.pk, name="p", secret_data="v2")

    hist = SecretHistory.objects.filter(secret__resource=resource, secret__user=owner)
    assert hist.count() == 1
    entry = hist.first()
    assert entry.created_by_id == owner.pk
    assert entry.data == "v1"  # guarda a versão anterior


def test_password_update_without_new_secret_keeps_history_empty(owner):
    from apps.core.services import PasswordService

    resource = make_password(owner, data="v1")
    PasswordService.update(owner, resource.pk, name="novo nome")  # sem secret_data

    assert SecretHistory.objects.filter(secret__resource=resource).count() == 0


def test_password_history_reflects_edits_not_shared_copies(owner, other):
    from apps.core.services import PasswordService

    resource = make_password(owner, data="v1")
    # cópia por-usuário (compartilhamento) NÃO deve contar como versão
    Secret.objects.create(resource=resource, user=other, data="v1")
    PasswordService.update(owner, resource.pk, name="p", secret_data="v2")
    PasswordService.update(owner, resource.pk, name="p", secret_data="v3")

    client = Client()
    client.force_login(owner)
    resp = client.get(reverse("password_detail", args=[resource.pk]))

    versions = list(resp.context["secret_versions"])
    assert len(versions) == 2
    assert all(v.created_by_id == owner.pk for v in versions)


def test_file_detail_shows_access_log_date(owner):
    fr = make_file(owner)
    FileAccessLog.objects.create(
        file_resource=fr, user=owner, action="view", ip_address="203.0.113.9",
    )
    client = Client()
    client.force_login(owner)

    resp = client.get(reverse("file_detail", args=[fr.pk]))

    assert resp.status_code == 200
    body = resp.content.decode()
    # a data/hora do log deve renderizar (dd/mm/aaaa hh:mm) — antes usava campo
    # inexistente (timestamp) e a célula ficava vazia
    import re
    assert re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", body)
    assert "203.0.113.9" in body


def test_client_ip_prefers_forwarded_for(db):
    from django.test import RequestFactory

    from apps.core.views_web import _client_ip

    req = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="198.51.100.7, 10.0.0.1", REMOTE_ADDR="10.0.0.1",
    )
    assert _client_ip(req) == "198.51.100.7"


def test_group_detail_lists_shared_folder(owner):
    group = _make_group(owner)
    folder = Folder.objects.create(name="Cofre RH", created_by=owner)
    client = Client()
    client.force_login(owner)
    client.post(
        reverse("folder_share", args=[folder.pk]),
        {"group_id": str(group.pk), "permission": "read"},
    )

    resp = client.get(reverse("group_detail", args=[group.pk]))

    types = {r["resource_type"] for r in resp.context["shared_resources"]}
    assert "folder" in types
    assert "Cofre RH" in resp.content.decode()
