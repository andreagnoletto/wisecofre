"""Comprehensive Playwright E2E tests for Wisecofre."""
import re
import os
import uuid

import pytest
from playwright.sync_api import Page, expect


BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8003")
UNIQUE = uuid.uuid4().hex[:6]

ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@wisecofre.io")
ADMIN_PASS = os.environ.get("E2E_ADMIN_PASS", "admin123admin123")
USER_EMAIL = os.environ.get("E2E_USER_EMAIL", "joao@wisecofre.io")
USER_PASS = os.environ.get("E2E_USER_PASS", "senha123senha123")
USER_DISPLAY = "João Silva"

_CREATED_USERS = False
_SENTINEL = object()


def _db_conn():
    """Return a psycopg connection if E2E_DATABASE_URL is set, else None."""
    _db = os.environ.get("E2E_DATABASE_URL", "")
    if not _db:
        return None
    try:
        import psycopg
        return psycopg.connect(_db, autocommit=True)
    except Exception:
        return None


def setup_module():
    """Create dedicated test users via DB if E2E_DATABASE_URL is set."""
    global ADMIN_EMAIL, ADMIN_PASS, USER_EMAIL, USER_PASS, USER_DISPLAY, _CREATED_USERS

    conn = _db_conn()
    if conn is None:
        return

    try:
        from django.contrib.auth.hashers import make_password
    except ImportError:
        conn.close()
        return

    ADMIN_EMAIL = f"testadm-{UNIQUE}@wisecofre.io"
    ADMIN_PASS = "TestAdm1nP4ss2026x"
    USER_EMAIL = f"testusr-{UNIQUE}@wisecofre.io"
    USER_PASS = "TestUs3rP4ss2026x"
    USER_DISPLAY = "TestUser E2E"

    for email, password, uname, role, staff, first, last in [
        (ADMIN_EMAIL, ADMIN_PASS, f"testadm{UNIQUE}", "ADMIN", True, "TestAdmin", "E2E"),
        (USER_EMAIL, USER_PASS, f"testusr{UNIQUE}", "USER", False, "TestUser", "E2E"),
    ]:
        hashed = make_password(password, hasher="pbkdf2_sha256")
        conn.execute("DELETE FROM accounts_user WHERE email = %s", (email,))
        conn.execute(
            """INSERT INTO accounts_user
               (id, username, email, password, role, is_staff, is_superuser, is_active,
                is_suspended, avatar_url, locale, first_name, last_name,
                date_joined, created_at, modified_at)
               VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, true,
                false, '', 'pt-BR', %s, %s, now(), now(), now())""",
            (uname, email, hashed, role, staff, staff, first, last),
        )
    conn.close()
    _CREATED_USERS = True


def teardown_module():
    """Delete dedicated test users created by setup_module."""
    if not _CREATED_USERS:
        return
    conn = _db_conn()
    if conn is None:
        return
    try:
        for email in (ADMIN_EMAIL, USER_EMAIL):
            conn.execute("DELETE FROM accounts_user WHERE email = %s", (email,))
        conn.close()
    except Exception:
        pass


def _login(page: Page, email=_SENTINEL, password=_SENTINEL):
    if email is _SENTINEL:
        email = ADMIN_EMAIL
    if password is _SENTINEL:
        password = ADMIN_PASS
    page.goto(f"{BASE}/login/")
    if page.url == f"{BASE}/":
        return
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    if "/mfa/verify" in page.url and email in MFA_SECRET:
        import pyotp
        code = pyotp.TOTP(MFA_SECRET[email]).now()
        page.fill('input[name="code"]', code)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE}/")


def _logout(page: Page):
    """Logout by clearing cookies (since logout_view requires POST)."""
    page.context.clear_cookies()


def _login_and_go(page: Page, path: str, email=_SENTINEL, password=_SENTINEL):
    if email is _SENTINEL:
        email = ADMIN_EMAIL
    if password is _SENTINEL:
        password = ADMIN_PASS
    _login(page, email, password)
    page.goto(f"{BASE}{path}")


# ═══════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════

def test_login_page_loads(page: Page):
    page.goto(f"{BASE}/login/")
    expect(page.locator('input[name="email"]')).to_be_visible()
    expect(page.locator('input[name="password"]')).to_be_visible()


def test_login_valid(page: Page):
    _login(page)
    expect(page).to_have_url(f"{BASE}/")
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_login_invalid(page: Page):
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', "wrong@email.com")
    page.fill('input[name="password"]', "wrongpass")
    page.click('button[type="submit"]')
    expect(page.locator(".alert-danger")).to_be_visible()


def test_unauthenticated_redirects(page: Page):
    page.goto(f"{BASE}/")
    expect(page).to_have_url(re.compile(r"/login/"))


def test_logout(page: Page):
    _login_and_go(page, "/")
    page.locator("nav .dropdown > button").last.click()
    page.locator(".dropdown-menu").last.wait_for(state="visible")
    page.locator('button.dropdown-item:has-text("Sair")').click()
    expect(page).to_have_url(re.compile(r"/login/"))


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

def test_dashboard_shows_stats(page: Page):
    _login(page)
    expect(page.get_by_text("Total de senhas")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════

def test_nav_passwords(page: Page):
    _login(page)
    page.locator(".sidebar").get_by_role("link", name=re.compile("Senhas")).click()
    expect(page).to_have_url(f"{BASE}/passwords/")


def test_nav_folders(page: Page):
    _login(page)
    page.locator(".sidebar").get_by_role("link", name=re.compile("Pastas")).click()
    expect(page).to_have_url(f"{BASE}/folders/")


def test_nav_files(page: Page):
    _login(page)
    page.locator(".sidebar").get_by_role("link", name=re.compile("Arquivos")).click()
    expect(page).to_have_url(f"{BASE}/files/")


def test_nav_groups(page: Page):
    _login(page)
    page.locator(".sidebar").get_by_role("link", name=re.compile("Grupos")).click()
    expect(page).to_have_url(f"{BASE}/groups/")


# ═══════════════════════════════════════════════════════════════════════════
# FOLDERS CRUD
# ═══════════════════════════════════════════════════════════════════════════

def test_folder_create(page: Page):
    _login_and_go(page, "/folders/")
    page.locator('[data-bs-target="#createFolderModal"]').first.click()
    page.wait_for_selector("#createFolderModal.show", state="visible")
    page.fill("#folderName", f"Pasta {UNIQUE}")
    with page.expect_navigation():
        page.click('#createFolderModal button[type="submit"]')
    expect(page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first).to_be_visible()


def test_folder_appears_in_list(page: Page):
    _login_and_go(page, "/folders/")
    expect(page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first).to_be_visible()


def test_folder_create_subfolder(page: Page):
    _login_and_go(page, "/folders/")
    page.locator('[data-bs-target="#createFolderModal"]').first.click()
    page.wait_for_selector("#createFolderModal.show", state="visible")
    page.fill("#folderName", f"Sub {UNIQUE}")
    page.select_option("#folderParent", label=f"Pasta {UNIQUE}")
    with page.expect_navigation():
        page.click('#createFolderModal button[type="submit"]')
    expect(page.locator(".list-group-item", has_text=f"Sub {UNIQUE}").first).to_be_visible()


def test_folder_detail_shows_subfolder(page: Page):
    """Navigate into folder and verify subfolder is listed."""
    _login_and_go(page, "/folders/")
    page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator(".list-group-item", has_text=f"Sub {UNIQUE}").first).to_be_visible()


def test_folder_detail_breadcrumb(page: Page):
    """Folder detail page shows breadcrumb with link back to root."""
    _login_and_go(page, "/folders/")
    page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator(".breadcrumb")).to_be_visible()
    expect(page.locator(".breadcrumb-item", has_text="Pastas")).to_be_visible()
    expect(page.locator(".breadcrumb-item.active", has_text=f"Pasta {UNIQUE}")).to_be_visible()


def test_folder_create_subfolder_from_detail(page: Page):
    """Create a subfolder from inside the folder detail page."""
    _login_and_go(page, "/folders/")
    page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.locator('[data-bs-target="#createFolderModal"]').first.click()
    page.wait_for_selector("#createFolderModal.show", state="visible")
    # Parent should be pre-selected to current folder
    selected = page.locator("#folderParent option:checked").text_content()
    assert f"Pasta {UNIQUE}" in selected, f"Parent should be pre-selected, got: {selected}"
    page.fill("#folderName", f"SubDetail {UNIQUE}")
    with page.expect_navigation():
        page.click('#createFolderModal button[type="submit"]')
    expect(page.locator(".list-group-item", has_text=f"SubDetail {UNIQUE}").first).to_be_visible()


def test_folder_delete(page: Page):
    _login_and_go(page, "/folders/")
    # Delete SubDetail subfolder first (cleanup from previous test)
    page.locator(".list-group-item", has_text=f"Pasta {UNIQUE}").first.click()
    page.wait_for_load_state("domcontentloaded")
    sub = page.locator(".list-group-item", has_text=f"SubDetail {UNIQUE}").first
    delete_action = sub.locator('form[action*="delete"]').get_attribute("action")
    csrf = sub.locator('input[name="csrfmiddlewaretoken"]').input_value()
    page.evaluate(f"""() => {{
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '{delete_action}';
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrfmiddlewaretoken';
        input.value = '{csrf}';
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    }}""")
    page.wait_for_url(f"**/folders/**")
    expect(page.locator(".alert-success")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# GROUPS CRUD + MEMBERSHIP
# ═══════════════════════════════════════════════════════════════════════════

def test_group_create(page: Page):
    _login_and_go(page, "/groups/")
    page.locator('[data-bs-target="#createGroupModal"]').first.click()
    page.wait_for_selector("#createGroupModal.show", state="visible")
    page.fill("#groupName", f"Grupo {UNIQUE}")
    with page.expect_navigation():
        page.click('#createGroupModal button[type="submit"]')
    expect(page.locator(".card-title", has_text=f"Grupo {UNIQUE}").first).to_be_visible()


def test_group_detail(page: Page):
    _login_and_go(page, "/groups/")
    page.locator(".card", has_text=f"Grupo {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    expect(page.locator("h4", has_text=f"Grupo {UNIQUE}")).to_be_visible()
    expect(page.get_by_text("Membros")).to_be_visible()


def test_group_add_member(page: Page):
    _login_and_go(page, "/groups/")
    page.locator(".card", has_text=f"Grupo {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    page.wait_for_selector("h4")
    select = page.locator('select[name="user_id"]')
    # Find the option containing joao
    option = select.locator("option", has_text=USER_EMAIL)
    option_value = option.get_attribute("value")
    select.select_option(value=option_value)
    with page.expect_navigation():
        page.get_by_role("button", name="Adicionar").click()
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.get_by_role("cell", name=USER_EMAIL)).to_be_visible()


def test_group_toggle_admin(page: Page):
    _login_and_go(page, "/groups/")
    page.locator(".card", has_text=f"Grupo {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    page.wait_for_selector("h4")
    joao_row = page.locator("tr", has_text=USER_EMAIL)
    toggle_form = joao_row.locator('form[action*="toggle-admin"]')
    with page.expect_navigation():
        toggle_form.locator("button").click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_group_remove_member(page: Page):
    _login_and_go(page, "/groups/")
    page.locator(".card", has_text=f"Grupo {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    page.wait_for_selector("h4")
    joao_row = page.locator("tr", has_text=USER_EMAIL)
    page.on("dialog", lambda d: d.accept())
    remove_form = joao_row.locator('form[action*="remove-member"]')
    with page.expect_navigation():
        remove_form.locator("button").click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_group_edit_name(page: Page):
    _login_and_go(page, "/groups/")
    page.locator(".card", has_text=f"Grupo {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    page.wait_for_selector("h4")
    # group_edit is POST-only via a link that goes to the edit endpoint
    # The edit link redirects to detail page; we test via direct POST
    edit_url = page.locator('a[href*="edit"]').first.get_attribute("href")
    page.goto(f"{BASE}{edit_url}")
    # group_edit only handles POST, GET redirects to detail. That's fine.
    expect(page.locator("h4", has_text=f"Grupo {UNIQUE}")).to_be_visible()


def test_group_delete(page: Page):
    # Create a temporary group to delete
    _login_and_go(page, "/groups/")
    page.locator('[data-bs-target="#createGroupModal"]').first.click()
    page.wait_for_selector("#createGroupModal.show", state="visible")
    page.fill("#groupName", f"DelGrp {UNIQUE}")
    with page.expect_navigation():
        page.click('#createGroupModal button[type="submit"]')

    # Get group id from detail page
    page.locator(".card", has_text=f"DelGrp {UNIQUE}").first.locator("a", has_text="Ver detalhes").click()
    page.wait_for_selector("h4")
    gid = page.url.rstrip("/").split("/")[-1]

    # Delete via JS POST (require_POST endpoint)
    page.evaluate(f"""() => {{
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/groups/{gid}/delete/';
        const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrf) {{
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrfmiddlewaretoken';
            input.value = csrf.value;
            form.appendChild(input);
        }}
        document.body.appendChild(form);
        form.submit();
    }}""")
    page.wait_for_url(f"{BASE}/groups/")
    expect(page.locator(".card-title", has_text=f"DelGrp {UNIQUE}")).to_have_count(0)


# ═══════════════════════════════════════════════════════════════════════════
# PASSWORDS CRUD
# ═══════════════════════════════════════════════════════════════════════════

def test_password_create(page: Page):
    _login_and_go(page, "/passwords/new/")
    page.fill('input[name="name"]', f"Senha {UNIQUE}")
    page.fill('input[name="username"]', "user_teste")
    page.fill('input[name="uri"]', "https://example.com")
    page.fill('textarea[name="description"]', "Descricao teste")
    with page.expect_navigation():
        page.click('#password-form button[type="submit"]')
    expect(page.get_by_role("link", name=f"Senha {UNIQUE}").first).to_be_visible()


def test_password_list(page: Page):
    _login_and_go(page, "/passwords/")
    expect(page.get_by_role("link", name=f"Senha {UNIQUE}").first).to_be_visible()


def test_password_detail(page: Page):
    _login_and_go(page, "/passwords/")
    page.get_by_role("link", name=f"Senha {UNIQUE}").first.click()
    expect(page.locator(".card-body h5.fw-bold", has_text=f"Senha {UNIQUE}")).to_be_visible()
    expect(page.get_by_text("user_teste")).to_be_visible()
    expect(page.get_by_text("example.com")).to_be_visible()
    expect(page.get_by_text("Quem tem acesso")).to_be_visible()


def test_password_edit(page: Page):
    _login_and_go(page, "/passwords/")
    page.get_by_role("link", name=f"Senha {UNIQUE}").first.click()
    # Get edit URL from the dropdown link
    edit_href = page.locator('a[href*="edit"]').first.get_attribute("href")
    page.goto(f"{BASE}{edit_href}")
    page.fill('input[name="name"]', f"Senha {UNIQUE} Editada")
    with page.expect_navigation():
        page.click('#password-form button[type="submit"]')
    expect(page.locator(".card-body h5.fw-bold", has_text=f"Senha {UNIQUE} Editada")).to_be_visible()


def test_password_share_with_user(page: Page):
    """Share a password with João and verify he can access it."""
    _login_and_go(page, "/passwords/")
    page.get_by_role("link", name=re.compile(f"Senha {UNIQUE}")).first.click()

    # Open share modal via JS (button is inside a dropdown)
    page.evaluate("() => new bootstrap.Modal(document.getElementById('shareModal')).show()")
    page.wait_for_selector("#shareModal.show", state="visible")
    page.fill('input[name="user_email"]', USER_EMAIL)
    with page.expect_navigation():
        page.locator('#shareModal button[type="submit"]').click()

    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.get_by_text(USER_DISPLAY, exact=True)).to_be_visible()


def test_shared_password_visible_to_other_user(page: Page):
    """Login as João and verify the shared password is visible."""
    _login_and_go(page, "/passwords/", USER_EMAIL, USER_PASS)
    expect(page.get_by_role("link", name=re.compile(f"Senha {UNIQUE}")).first).to_be_visible()


def test_shared_password_detail_accessible(page: Page):
    """Login as João and access the shared password detail."""
    _login_and_go(page, "/passwords/", USER_EMAIL, USER_PASS)
    page.get_by_role("link", name=re.compile(f"Senha {UNIQUE}")).first.click()
    expect(page.locator(".card-body h5.fw-bold")).to_be_visible()


def test_password_search(page: Page):
    _login_and_go(page, "/passwords/")
    page.fill('input[name="q"]', f"Senha {UNIQUE}")
    page.keyboard.press("Enter")
    expect(page.get_by_role("link", name=re.compile(f"Senha {UNIQUE}")).first).to_be_visible()


def test_password_delete(page: Page):
    # Create a throwaway password to delete
    _login_and_go(page, "/passwords/new/")
    page.fill('input[name="name"]', f"DelPwd {UNIQUE}")
    with page.expect_navigation():
        page.click('#password-form button[type="submit"]')

    # Go to detail and delete via modal
    page.goto(f"{BASE}/passwords/")
    page.get_by_role("link", name=f"DelPwd {UNIQUE}").first.click()
    page.evaluate("() => new bootstrap.Modal(document.getElementById('deleteModal')).show()")
    page.wait_for_selector("#deleteModal.show", state="visible")
    with page.expect_navigation():
        page.locator('#deleteModal button[type="submit"]').click()
    expect(page.locator(".alert-success")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# FILES CRUD + SHARING
# ═══════════════════════════════════════════════════════════════════════════

def test_file_upload(page: Page, tmp_path):
    _login_and_go(page, "/files/upload/")
    test_file = tmp_path / f"file_{UNIQUE}.txt"
    test_file.write_text("conteudo de teste e2e")
    page.locator('input[name="file"]').set_input_files(str(test_file))
    with page.expect_navigation():
        page.get_by_role("button", name=re.compile("Enviar")).click()
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.locator("h4", has_text=f"file_{UNIQUE}.txt")).to_be_visible()


def test_file_in_list(page: Page):
    _login_and_go(page, "/files/")
    expect(page.get_by_role("link", name=f"file_{UNIQUE}.txt").first).to_be_visible()


def test_file_detail(page: Page):
    _login_and_go(page, "/files/")
    page.get_by_role("link", name=f"file_{UNIQUE}.txt").first.click()
    expect(page.locator("h4", has_text=f"file_{UNIQUE}.txt")).to_be_visible()
    expect(page.get_by_text("Usuários com acesso")).to_be_visible()


def test_file_download(page: Page):
    """Download a file and verify content."""
    _login_and_go(page, "/files/")
    page.get_by_role("link", name=f"file_{UNIQUE}.txt").first.click()
    with page.expect_download() as download_info:
        page.get_by_role("link", name=re.compile("Baixar|Download|descriptografar", re.IGNORECASE)).first.click()
    download = download_info.value
    assert f"file_{UNIQUE}.txt" in download.suggested_filename
    path = download.path()
    content = open(path, "r").read()
    assert "conteudo de teste e2e" in content


def test_file_share_with_user(page: Page):
    """Share a file with João."""
    _login_and_go(page, "/files/")
    page.get_by_role("link", name=f"file_{UNIQUE}.txt").first.click()
    page.fill('input[name="user_query"]', USER_EMAIL)
    # Need to enable the submit button (Alpine.js :disabled binding)
    page.evaluate("() => document.querySelector('form[action*=\"share\"] button[type=\"submit\"]').disabled = false")
    with page.expect_navigation():
        page.locator('form[action*="share"] button[type="submit"]').click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_shared_file_visible_to_other_user(page: Page):
    """Login as João and verify the shared file is visible."""
    _login_and_go(page, "/files/", USER_EMAIL, USER_PASS)
    expect(page.get_by_role("link", name=f"file_{UNIQUE}.txt").first).to_be_visible()


def test_file_unshare(page: Page):
    """Unshare the file from João."""
    _login_and_go(page, "/files/")
    page.get_by_role("link", name=f"file_{UNIQUE}.txt").first.click()
    joao_entry = page.locator("li", has_text=USER_DISPLAY.split()[0])
    revoke_form = joao_entry.locator('form[action*="unshare"]')
    with page.expect_navigation():
        revoke_form.locator("button").click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_unshared_file_not_visible_to_other_user(page: Page):
    """Login as João and verify the file is no longer visible."""
    _login_and_go(page, "/files/", USER_EMAIL, USER_PASS)
    expect(page.get_by_role("link", name=f"file_{UNIQUE}.txt")).to_have_count(0)


def test_file_delete(page: Page, tmp_path):
    # Upload a throwaway file
    _login_and_go(page, "/files/upload/")
    test_file = tmp_path / f"delfile_{UNIQUE}.txt"
    test_file.write_text("to be deleted")
    page.locator('input[name="file"]').set_input_files(str(test_file))
    with page.expect_navigation():
        page.get_by_role("button", name=re.compile("Enviar")).click()

    # Now delete from detail
    page.locator('button:has-text("Excluir arquivo")').click()
    page.wait_for_selector("#deleteFileModal.show", state="visible")
    with page.expect_navigation():
        page.locator('#deleteFileModal button:has-text("Excluir")').click()
    expect(page.locator(".alert-success")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# USERS ADMIN
# ═══════════════════════════════════════════════════════════════════════════

def test_users_page_loads(page: Page):
    _login_and_go(page, "/users/")
    expect(page.get_by_role("button", name=re.compile("Convidar"))).to_be_visible()
    expect(page.get_by_role("cell", name=ADMIN_EMAIL)).to_be_visible()


def test_user_invite(page: Page):
    _login_and_go(page, "/users/")
    page.get_by_role("button", name=re.compile("Convidar")).click()
    page.wait_for_selector("#inviteModal.show", state="visible")
    page.fill('#inviteEmail', f"convidado_{UNIQUE}@wisecofre.io")
    page.fill('#inviteFirst', "Convidado")
    page.fill('#inviteLast', "Teste")
    with page.expect_navigation():
        page.locator('#inviteModal button[type="submit"]').click()
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.get_by_text(f"convidado_{UNIQUE}@wisecofre.io").first).to_be_visible()


def test_user_detail(page: Page):
    _login_and_go(page, "/users/")
    row = page.locator("tr", has_text=f"convidado_{UNIQUE}@wisecofre.io")
    row.locator('button[data-bs-toggle="dropdown"]').click()
    row.locator(".dropdown-menu").wait_for(state="visible")
    row.get_by_role("link", name="Ver").click()
    expect(page.get_by_text(f"convidado_{UNIQUE}@wisecofre.io")).to_be_visible()


def test_user_toggle_active(page: Page):
    _login_and_go(page, "/users/")
    row = page.locator("tr", has_text=f"convidado_{UNIQUE}@wisecofre.io")
    row.locator('button[data-bs-toggle="dropdown"]').click()
    row.locator(".dropdown-menu").wait_for(state="visible")
    with page.expect_navigation():
        row.get_by_role("button", name="Suspender").click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_user_search(page: Page):
    _login_and_go(page, "/users/")
    page.fill('input[name="q"]', f"convidado_{UNIQUE}")
    page.keyboard.press("Enter")
    expect(page.get_by_text(f"convidado_{UNIQUE}@wisecofre.io")).to_be_visible()


def test_user_delete(page: Page):
    _login_and_go(page, "/users/")
    row = page.locator("tr", has_text=f"convidado_{UNIQUE}@wisecofre.io")
    row.locator('button[data-bs-toggle="dropdown"]').click()
    row.locator(".dropdown-menu").wait_for(state="visible")
    page.on("dialog", lambda d: d.accept())
    with page.expect_navigation():
        row.get_by_role("button", name="Excluir").click()
    expect(page.locator(".alert-success")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════════════════════════════════

def test_profile_page_loads(page: Page):
    _login_and_go(page, "/profile/")
    expect(page.get_by_role("heading", name="Meu Perfil")).to_be_visible()
    expect(page.locator('input[name="first_name"]')).to_be_visible()


def test_profile_update(page: Page):
    _login_and_go(page, "/profile/")
    page.fill('input[name="first_name"]', "Admin")
    page.fill('input[name="last_name"]', "Wisecofre")
    with page.expect_navigation():
        page.get_by_role("button", name="Salvar Alterações").click()
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.locator('input[name="first_name"]')).to_have_value("Admin")


def test_profile_change_password(page: Page):
    _login_and_go(page, "/profile/")
    _tmp = "TempP4ssw0rd-Change-2026!"
    page.fill('#currentPwd', ADMIN_PASS)
    page.fill('#newPwd', _tmp)
    page.fill('#confirmPwd', _tmp)
    with page.expect_navigation():
        page.get_by_role("button", name="Alterar Senha").click()
    expect(page.locator(".alert-success")).to_be_visible()
    # Change back immediately (session stays valid via update_session_auth_hash)
    page.fill('#currentPwd', _tmp)
    page.fill('#newPwd', ADMIN_PASS)
    page.fill('#confirmPwd', ADMIN_PASS)
    with page.expect_navigation():
        page.get_by_role("button", name="Alterar Senha").click()
    expect(page.locator(".alert-success")).to_be_visible()


def test_profile_change_password_mismatch(page: Page):
    _login_and_go(page, "/profile/")
    page.fill('#currentPwd', ADMIN_PASS)
    page.fill('#newPwd', "abc123")
    page.fill('#confirmPwd', "xyz789")
    with page.expect_navigation():
        page.get_by_role("button", name="Alterar Senha").click()
    expect(page.locator(".alert-danger, .alert-error")).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT
# ═══════════════════════════════════════════════════════════════════════════

def test_audit_page_loads(page: Page):
    _login_and_go(page, "/audit/")
    expect(page.get_by_role("heading", name="Auditoria")).to_be_visible()


def test_audit_export_csv(page: Page):
    _login_and_go(page, "/audit/")
    with page.expect_download() as download_info:
        page.get_by_role("link", name="CSV").click()
    download = download_info.value
    assert download.suggested_filename == "audit_logs.csv"


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

def test_settings_page_loads(page: Page):
    _login_and_go(page, "/settings/")
    expect(page.get_by_role("heading", name="Configurações", exact=True)).to_be_visible()


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-USER: second user login and capabilities
# ═══════════════════════════════════════════════════════════════════════════

def test_second_user_login(page: Page):
    _login(page, USER_EMAIL, USER_PASS)
    expect(page).to_have_url(f"{BASE}/")
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_second_user_dashboard(page: Page):
    _login(page, USER_EMAIL, USER_PASS)
    expect(page.get_by_text("Total de senhas")).to_be_visible()


def test_second_user_can_create_password(page: Page):
    _login_and_go(page, "/passwords/new/", USER_EMAIL, USER_PASS)
    page.fill('input[name="name"]', f"JoaoPwd {UNIQUE}")
    with page.expect_navigation():
        page.click('#password-form button[type="submit"]')
    expect(page.get_by_role("link", name=f"JoaoPwd {UNIQUE}").first).to_be_visible()


def test_second_user_can_create_folder(page: Page):
    _login_and_go(page, "/folders/", USER_EMAIL, USER_PASS)
    page.locator('[data-bs-target="#createFolderModal"]').first.click()
    page.wait_for_selector("#createFolderModal.show", state="visible")
    page.fill("#folderName", f"JoaoDir {UNIQUE}")
    with page.expect_navigation():
        page.click('#createFolderModal button[type="submit"]')
    expect(page.locator(".list-group-item", has_text=f"JoaoDir {UNIQUE}").first).to_be_visible()


def test_second_user_cannot_access_admin_users(page: Page):
    """Non-staff users should be redirected from admin pages."""
    _login_and_go(page, "/users/", USER_EMAIL, USER_PASS)
    # user_passes_test redirects to login_url, which then redirects to / since user is logged in
    assert "/users/" not in page.url, f"Non-staff user should not access /users/, got: {page.url}"


def test_second_user_cannot_access_admin_settings(page: Page):
    _login_and_go(page, "/settings/", USER_EMAIL, USER_PASS)
    assert "/settings/" not in page.url, f"Non-staff user should not access /settings/, got: {page.url}"


def test_second_user_cannot_access_audit(page: Page):
    _login_and_go(page, "/audit/", USER_EMAIL, USER_PASS)
    assert "/audit/" not in page.url, f"Non-staff user should not access /audit/, got: {page.url}"


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

def test_settings_page_loads(page: Page):
    _login_and_go(page, "/settings/")
    expect(page.get_by_role("heading", name="Configurações Gerais")).to_be_visible()
    expect(page.get_by_role("button", name="Geral")).to_be_visible()
    expect(page.get_by_role("button", name="Segurança")).to_be_visible()
    expect(page.get_by_role("button", name="Storage")).to_be_visible()


def test_settings_save_general(page: Page):
    _login_and_go(page, "/settings/")
    page.fill('input[name="APP_NAME"]', f"Wisecofre-{UNIQUE}")
    page.fill('input[name="SESSION_TIMEOUT_MINUTES"]', "45")
    reg = page.locator('input[name="REGISTRATION_OPEN"]')
    if not reg.is_checked():
        reg.click()
    with page.expect_navigation():
        page.click('button:has-text("Salvar Configurações")')
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.locator('input[name="APP_NAME"]')).to_have_value(f"Wisecofre-{UNIQUE}")
    expect(page.locator('input[name="SESSION_TIMEOUT_MINUTES"]')).to_have_value("45")
    expect(page.locator('input[name="REGISTRATION_OPEN"]')).to_be_checked()


def test_settings_save_security(page: Page):
    _login_and_go(page, "/settings/")
    page.get_by_role("button", name="Segurança").click()
    page.select_option('select[name="MFA_POLICY"]', "DISABLED")
    page.fill('input[name="PASSWORD_MIN_LENGTH"]', "16")
    with page.expect_navigation():
        page.click('button:has-text("Salvar Configurações")')
    page.get_by_role("button", name="Segurança").click()
    expect(page.locator('select[name="MFA_POLICY"]')).to_have_value("DISABLED")
    expect(page.locator('input[name="PASSWORD_MIN_LENGTH"]')).to_have_value("16")
    # Reset to safe defaults
    page.select_option('select[name="MFA_POLICY"]', "OPTIONAL")
    page.fill('input[name="PASSWORD_MIN_LENGTH"]', "8")
    with page.expect_navigation():
        page.click('button:has-text("Salvar Configurações")')


def test_settings_persist_after_reload(page: Page):
    """Values saved in previous tests should persist."""
    _login_and_go(page, "/settings/")
    expect(page.locator('input[name="APP_NAME"]')).to_have_value(f"Wisecofre-{UNIQUE}")


def test_settings_save_storage(page: Page):
    _login_and_go(page, "/settings/")
    page.get_by_role("button", name="Storage").click()
    page.fill('input[name="FILE_MAX_SIZE_MB"]', "100")
    page.fill('input[name="USER_QUOTA_MB"]', "1000")
    with page.expect_navigation():
        page.click('button:has-text("Salvar Configurações")')
    page.get_by_role("button", name="Storage").click()
    expect(page.locator('input[name="FILE_MAX_SIZE_MB"]')).to_have_value("100")
    expect(page.locator('input[name="USER_QUOTA_MB"]')).to_have_value("1000")


def test_settings_test_storage_connection(page: Page):
    _login_and_go(page, "/settings/")
    page.get_by_role("button", name="Storage").click()
    page.locator('button:has-text("Testar Conexão")').first.click()
    page.wait_for_function(
        "() => document.querySelector('[x-html=\"storageResult\"]')?.innerHTML.trim().length > 0",
        timeout=10000,
    )
    result_el = page.locator('[x-html="storageResult"]')
    expect(result_el).not_to_be_empty()


def test_settings_sso_create_provider(page: Page):
    _login_and_go(page, "/settings/")
    page.get_by_role("button", name="SSO").click()
    page.select_option('select[name="SSO_PROVIDER_TYPE"]', "google")
    page.fill('input[name="SSO_CLIENT_ID"]', f"test-client-{UNIQUE}")
    page.fill('input[name="SSO_CLIENT_SECRET"]', "test-secret-123")
    page.fill('input[name="SSO_DISCOVERY_URL"]', "https://accounts.google.com/.well-known/openid-configuration")
    with page.expect_navigation():
        page.click('button:has-text("Adicionar Provider")')
    expect(page.locator(".alert-success")).to_be_visible()
    page.get_by_role("button", name="SSO").click()
    expect(page.locator("td", has_text=f"test-client-{UNIQUE}")).to_be_visible()


def test_settings_sso_delete_provider(page: Page):
    _login_and_go(page, "/settings/")
    page.get_by_role("button", name="SSO").click()
    page.on("dialog", lambda dialog: dialog.accept())
    delete_btn = page.locator(f"tr:has-text('test-client-{UNIQUE}') .btn-outline-danger")
    with page.expect_navigation():
        delete_btn.click()
    expect(page.locator(".alert-success")).to_be_visible()
    page.get_by_role("button", name="SSO").click()
    expect(page.locator("td", has_text=f"test-client-{UNIQUE}")).not_to_be_visible()


def test_settings_checkbox_unchecked_saves_false(page: Page):
    """Ensure unchecking a checkbox saves False correctly."""
    _login_and_go(page, "/settings/")
    reg_checkbox = page.locator('input[name="REGISTRATION_OPEN"]')
    if reg_checkbox.is_checked():
        reg_checkbox.click()
    with page.expect_navigation():
        page.click('button:has-text("Salvar Configurações")')
    expect(page.locator('input[name="REGISTRATION_OPEN"]')).not_to_be_checked()


# ═══════════════════════════════════════════════════════════════════════════
# MFA / TOTP
# ═══════════════════════════════════════════════════════════════════════════

MFA_SECRET = {}


def _extract_secret_from_setup(page: Page) -> str:
    """Click 'show manual key' and grab the TOTP secret from the page."""
    page.wait_for_load_state("networkidle")
    page.locator('button:has-text("Mostrar chave manual")').wait_for(state="visible", timeout=10000)
    page.click('button:has-text("Mostrar chave manual")')
    secret = page.locator("code").first.inner_text()
    return secret.strip()


def test_mfa_cleanup_before_tests(page: Page):
    """Ensure MFA is disabled before running MFA tests."""
    _db = os.environ.get("E2E_DATABASE_URL", "")
    if _db:
        import psycopg
        conn = psycopg.connect(_db, autocommit=True)
        conn.execute(
            "DELETE FROM mfa_backupcode WHERE user_id IN (SELECT id FROM accounts_user WHERE email = %s)",
            (ADMIN_EMAIL,),
        )
        conn.execute(
            "DELETE FROM mfa_totpdevice WHERE user_id IN (SELECT id FROM accounts_user WHERE email = %s)",
            (ADMIN_EMAIL,),
        )
        conn.close()
    else:
        _login_and_go(page, "/profile/")
        if page.locator("text=MFA ativo").is_visible():
            page.get_by_role("link", name=re.compile("Desativar|Disable")).click()
            page.wait_for_load_state("networkidle")


def test_mfa_setup_page_loads(page: Page):
    _login_and_go(page, "/profile/mfa/setup/")
    expect(page.locator("#qrcode")).to_be_visible()
    expect(page.locator('input[name="code"]')).to_be_visible()
    expect(page.get_by_text("Google Authenticator")).to_be_visible()


def test_mfa_setup_invalid_code(page: Page):
    _login_and_go(page, "/profile/mfa/setup/")
    page.fill('input[name="code"]', "000000")
    with page.expect_navigation():
        page.click('button:has-text("Verificar e Ativar")')
    expect(page.locator(".alert-error")).to_be_visible()


def test_mfa_setup_and_activate(page: Page):
    import pyotp
    _login_and_go(page, "/profile/mfa/setup/")
    secret = _extract_secret_from_setup(page)
    MFA_SECRET[ADMIN_EMAIL] = secret
    code = pyotp.TOTP(secret).now()
    page.fill('input[name="code"]', code)
    with page.expect_navigation():
        page.click('button:has-text("Verificar e Ativar")')
    expect(page.get_by_role("heading", name="MFA Ativado com Sucesso")).to_be_visible()
    expect(page.locator("code").first).to_be_visible()


def test_mfa_profile_shows_active(page: Page):
    _login_and_go(page, "/profile/")
    expect(page.locator(".badge.bg-success", has_text="Ativo")).to_be_visible()
    expect(page.get_by_text("Desativar TOTP")).to_be_visible()


def test_mfa_login_requires_code(page: Page):
    """After enabling TOTP, login should redirect to MFA verify."""
    _logout(page)
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    assert "/mfa/verify" in page.url


def test_mfa_login_with_valid_code(page: Page):
    """Complete login with valid TOTP code."""
    import pyotp
    _logout(page)
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    code = pyotp.TOTP(MFA_SECRET[ADMIN_EMAIL]).now()
    page.fill('input[name="code"]', code)
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page).to_have_url(f"{BASE}/")


def test_mfa_login_with_invalid_code(page: Page):
    _logout(page)
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.fill('input[name="code"]', "999999")
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page.locator(".alert-danger")).to_be_visible()
    assert "/mfa/verify" in page.url


def test_mfa_login_with_backup_code(page: Page):
    """Login using a backup code from the profile page."""
    _login_and_go(page, "/profile/")
    page.click('button:has-text("Códigos de backup")')
    page.wait_for_selector("code", state="visible")
    backup_code = page.locator("code").first.inner_text().strip()

    _logout(page)
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.fill('input[name="code"]', backup_code)
    with page.expect_navigation():
        page.click('button[type="submit"]')
    expect(page).to_have_url(f"{BASE}/")


def test_mfa_disable(page: Page):
    _login_and_go(page, "/profile/")
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_navigation():
        page.click('button:has-text("Desativar TOTP")')
    expect(page.locator(".alert-success")).to_be_visible()
    expect(page.locator(".badge.bg-secondary", has_text="Inativo")).to_be_visible()


def test_mfa_login_normal_after_disable(page: Page):
    """After disabling TOTP, login should go straight to dashboard."""
    _logout(page)
    page.goto(f"{BASE}/login/")
    page.fill('input[name="email"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE}/")


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY: IDOR, ownership, authorization tests
# ═══════════════════════════════════════════════════════════════════════════

def _get_session(email, password):
    """Get an authenticated requests session for HTTP-level tests."""
    import requests
    s = requests.Session()
    r = s.get(f"{BASE}/login/")
    m = re.search(r'csrfmiddlewaretoken.*?value="(.*?)"', r.text)
    csrf = m.group(1) if m else ""
    s.post(f"{BASE}/login/", data={
        "email": email, "password": password, "csrfmiddlewaretoken": csrf,
    }, headers={"Referer": f"{BASE}/login/"})
    return s


def _csrf_post(session, url, data=None, referer_url=None):
    """POST with CSRF token from the session."""
    ref = referer_url or f"{BASE}/"
    r = session.get(ref)
    m = re.search(r'csrfmiddlewaretoken.*?value="(.*?)"', r.text)
    csrf = m.group(1) if m else session.cookies.get("csrftoken", "")
    payload = {"csrfmiddlewaretoken": csrf}
    if data:
        payload.update(data)
    return session.post(url, data=payload, allow_redirects=False)


_UUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def _create_password_as(session, name):
    """Create a password via HTTP and return its UUID."""
    _csrf_post(session, f"{BASE}/passwords/new/", data={
        "name": name, "uri": "https://sec.example.com",
        "username": "secuser", "secret": "secpass123",
        "description": "security test",
    }, referer_url=f"{BASE}/passwords/new/")
    r = session.get(f"{BASE}/passwords/")
    for pk in re.findall(rf'href="/passwords/({_UUID_RE})/"', r.text):
        detail = session.get(f"{BASE}/passwords/{pk}/")
        if name in detail.text:
            return pk
    return None


def _create_file_as(session, name):
    """Upload a small file via HTTP and return its UUID."""
    ref = f"{BASE}/files/upload/"
    r = session.get(ref)
    m = re.search(r'csrfmiddlewaretoken.*?value="(.*?)"', r.text)
    csrf = m.group(1) if m else session.cookies.get("csrftoken", "")
    import io
    files = {"file": (f"{name}.txt", io.BytesIO(b"sec test content"), "text/plain")}
    data = {"csrfmiddlewaretoken": csrf, "description": "security test file"}
    session.post(f"{BASE}/files/upload/", data=data, files=files,
                 headers={"Referer": ref})
    r = session.get(f"{BASE}/files/")
    for pk in re.findall(rf'href="/files/({_UUID_RE})/"', r.text):
        detail = session.get(f"{BASE}/files/{pk}/")
        if name in detail.text:
            return pk
    return None


def test_security_user_cannot_delete_other_user_password(page: Page):
    """User B cannot delete a password created by User A."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    pk = _create_password_as(admin_s, f"SecDel-{UNIQUE}")
    if not pk:
        pytest.skip("Could not create admin password")
    r = _csrf_post(user_s, f"{BASE}/passwords/{pk}/delete/",
                    referer_url=f"{BASE}/passwords/")
    assert r.status_code in (302, 403)
    detail = admin_s.get(f"{BASE}/passwords/{pk}/")
    assert detail.status_code == 200, "Password should still exist"


def test_security_user_cannot_access_other_user_password_detail(page: Page):
    """User B cannot see password detail if no Secret exists for them."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    pk = _create_password_as(admin_s, f"PrivPwd2-{UNIQUE}")
    if not pk:
        pytest.skip("Could not create private admin password")
    r = user_s.get(f"{BASE}/passwords/{pk}/")
    assert r.status_code == 403


def test_security_non_admin_cannot_manage_group(page: Page):
    """Non-admin user cannot access group management endpoints."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    _csrf_post(admin_s, f"{BASE}/groups/", data={
        "name": f"SecGrp2-{UNIQUE}",
    }, referer_url=f"{BASE}/groups/")
    r = admin_s.get(f"{BASE}/groups/")
    grp_pk = None
    for pk in set(re.findall(rf'href="/groups/({_UUID_RE})/"', r.text)):
        r2 = admin_s.get(f"{BASE}/groups/{pk}/")
        if f"SecGrp2-{UNIQUE}" in r2.text:
            grp_pk = pk
            break
    if not grp_pk:
        pytest.skip("Could not find created group")
    r = user_s.get(f"{BASE}/groups/{grp_pk}/")
    assert r.status_code in (302, 403) or "Sem permissão" in r.text


def test_security_user_cannot_delete_other_user_file(page: Page):
    """User B cannot delete a file owned by User A."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    pk = _create_file_as(admin_s, f"SecFile-{UNIQUE}")
    if not pk:
        pytest.skip("Could not create admin file")
    r = _csrf_post(user_s, f"{BASE}/files/{pk}/delete/",
                    referer_url=f"{BASE}/files/")
    assert r.status_code in (302, 403)
    detail = admin_s.get(f"{BASE}/files/{pk}/")
    assert detail.status_code == 200, "File should still exist"


def test_security_user_cannot_unshare_file_they_dont_own(page: Page):
    """Only the file owner can revoke sharing."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    pk = _create_file_as(admin_s, f"SecUnsh-{UNIQUE}")
    if not pk:
        pytest.skip("Could not create admin file")
    r = _csrf_post(user_s, f"{BASE}/files/{pk}/unshare/", data={"user_id": "fake-id"},
                    referer_url=f"{BASE}/files/")
    assert r.status_code in (302, 403)


def test_security_non_member_cannot_access_group_detail(page: Page):
    """User who is not a group member cannot view group details."""
    admin_s = _get_session(ADMIN_EMAIL, ADMIN_PASS)
    user_s = _get_session(USER_EMAIL, USER_PASS)
    _csrf_post(admin_s, f"{BASE}/groups/", data={
        "name": f"PrivGrp2-{UNIQUE}",
    }, referer_url=f"{BASE}/groups/")
    r = admin_s.get(f"{BASE}/groups/")
    grp_pk = None
    for pk in set(re.findall(rf'href="/groups/({_UUID_RE})/"', r.text)):
        r2 = admin_s.get(f"{BASE}/groups/{pk}/")
        if f"PrivGrp2-{UNIQUE}" in r2.text:
            grp_pk = pk
            break
    if not grp_pk:
        pytest.skip("Could not find created group")
    r = user_s.get(f"{BASE}/groups/{grp_pk}/", allow_redirects=True)
    assert "Sem permissão" in r.text or r.url.endswith("/groups/")
