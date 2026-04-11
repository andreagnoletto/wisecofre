from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.models import GpgKey, User
from apps.audit.models import ActionLog
from apps.core.models import SystemConfiguration
from apps.core.services import (
    FileService, FolderService, GroupService, PasswordService,
)
from apps.files.models import FileAccessLog, FileResource, FileSecret
from apps.folders.models import Folder
from apps.groups.models import Group, GroupUser
from apps.resources.models import Favorite, Resource, ResourceType, Secret, Tag


# ── Helpers ───────────────────────────────────────────────────────────────

CHECKBOX_FIELDS = {
    "REGISTRATION_OPEN", "SMTP_USE_TLS", "LDAP_ENABLED", "LDAP_USE_TLS",
}

CONFIG_FIELDS = {
    "APP_NAME", "APP_BASE_URL", "REGISTRATION_OPEN", "SESSION_TIMEOUT_MINUTES",
    "MFA_POLICY", "ACCOUNT_RECOVERY_POLICY", "PASSWORD_MIN_LENGTH", "PASSWORD_MIN_ENTROPY",
    "EMAIL_SENDER_NAME", "EMAIL_SENDER_ADDRESS", "SMTP_HOST", "SMTP_PORT",
    "SMTP_USE_TLS", "SMTP_USER", "SMTP_PASSWORD",
    "MINIO_ENDPOINT", "MINIO_BUCKET", "FILE_MAX_SIZE_MB", "USER_QUOTA_MB",
    "LDAP_ENABLED", "LDAP_HOST", "LDAP_PORT", "LDAP_USE_TLS",
    "LDAP_BIND_DN", "LDAP_BIND_PASSWORD", "LDAP_BASE_DN", "LDAP_USER_FILTER",
    "LDAP_SYNC_INTERVAL",
}

SSO_FIELDS = {"SSO_PROVIDER_TYPE", "SSO_CLIENT_ID", "SSO_CLIENT_SECRET",
              "SSO_TENANT_ID", "SSO_DISCOVERY_URL", "SSO_ENABLED"}

CONFIG_DEFAULTS = {
    "APP_NAME": "Wisecofre", "APP_BASE_URL": "", "REGISTRATION_OPEN": False,
    "SESSION_TIMEOUT_MINUTES": 30, "MFA_POLICY": "OPTIONAL",
    "ACCOUNT_RECOVERY_POLICY": "EMAIL", "PASSWORD_MIN_LENGTH": 12,
    "PASSWORD_MIN_ENTROPY": 50, "EMAIL_SENDER_NAME": "Wisecofre",
    "EMAIL_SENDER_ADDRESS": "", "SMTP_HOST": "", "SMTP_PORT": 587,
    "SMTP_USE_TLS": True, "SMTP_USER": "", "SMTP_PASSWORD": "",
    "MINIO_ENDPOINT": "", "MINIO_BUCKET": "wisecofre-files",
    "FILE_MAX_SIZE_MB": 50, "USER_QUOTA_MB": 500,
    "LDAP_ENABLED": False, "LDAP_HOST": "", "LDAP_PORT": 389,
    "LDAP_USE_TLS": False, "LDAP_BIND_DN": "", "LDAP_BIND_PASSWORD": "",
    "LDAP_BASE_DN": "", "LDAP_USER_FILTER": "", "LDAP_SYNC_INTERVAL": 60,
}


def get_config(key, default=None):
    try:
        return SystemConfiguration.objects.get(key=key).value
    except SystemConfiguration.DoesNotExist:
        return default if default is not None else CONFIG_DEFAULTS.get(key)


def is_staff(user):
    return user.is_staff


def _safe_next(request):
    """Validate next parameter to prevent open redirect."""
    next_url = request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return "dashboard"


def _set_session_timeout(request):
    timeout = get_config("SESSION_TIMEOUT_MINUTES", 30)
    try:
        request.session.set_expiry(int(timeout) * 60)
    except (ValueError, TypeError):
        request.session.set_expiry(1800)


# ── Auth ──────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            next_url = _safe_next(request)
            if user.totp_enabled:
                request.session["mfa_user_id"] = str(user.pk)
                request.session["mfa_next"] = next_url
                return redirect("mfa_verify")
            login(request, user)
            _set_session_timeout(request)
            mfa_policy = get_config("MFA_POLICY", "OPTIONAL")
            if mfa_policy == "REQUIRED" and not user.totp_enabled:
                messages.warning(request, "A política de segurança exige ativação do MFA.")
                return redirect("mfa_setup")
            return redirect(next_url)
        error = "Email ou senha inválidos."
    return render(request, "auth/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


# ── Dashboard ─────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    user = request.user
    total_passwords = Secret.objects.filter(user=user).count()
    shared_with_me = Secret.objects.filter(user=user).exclude(resource__created_by=user).count()
    total_files = FileSecret.objects.filter(user=user).count()
    expired_resources = Resource.objects.filter(
        secrets__user=user, expired_at__isnull=False
    ).distinct()[:5]
    if user.is_staff:
        recent_logs = ActionLog.objects.select_related("user").order_by("-created_at")[:10]
    else:
        recent_logs = ActionLog.objects.filter(user=user).order_by("-created_at")[:10]
    return render(request, "dashboard.html", {
        "total_passwords": total_passwords,
        "shared_with_me": shared_with_me,
        "total_files": total_files,
        "expired_count": expired_resources.count(),
        "expired_resources": expired_resources,
        "recent_logs": recent_logs,
    })


# ── Passwords ─────────────────────────────────────────────────────────────

@login_required
def password_list(request):
    secrets = Secret.objects.filter(
        user=request.user, resource__deleted_at__isnull=True,
    ).select_related("resource__resource_type", "resource__folder")
    search = request.GET.get("q", "") or request.GET.get("search", "")
    if search:
        secrets = secrets.filter(resource__name__icontains=search)
    filter_type = request.GET.get("filter", "")
    if filter_type == "mine":
        secrets = secrets.filter(resource__created_by=request.user)
    elif filter_type == "shared":
        secrets = secrets.exclude(resource__created_by=request.user)
    elif filter_type == "expired":
        from django.utils import timezone
        secrets = secrets.filter(resource__expired_at__lt=timezone.now())
    elif filter_type == "favorites":
        fav_ids = Favorite.objects.filter(user=request.user).values_list("resource_id", flat=True)
        secrets = secrets.filter(resource_id__in=fav_ids)
    resources = [s.resource for s in secrets]
    return render(request, "passwords/list.html", {
        "resources": resources, "search": search, "current_filter": filter_type,
    })


@login_required
def password_create(request):
    if request.method == "POST":
        try:
            PasswordService.create(
                request.user,
                name=request.POST.get("name", "").strip(),
                secret_data=request.POST.get("secret", ""),
                username=request.POST.get("username", "").strip() or None,
                uri=request.POST.get("uri", "").strip() or None,
                description=request.POST.get("description", "").strip() or None,
                folder_id=request.POST.get("folder") or None,
                tags_raw=request.POST.get("tags", "").strip(),
            )
            messages.success(request, "Senha criada.")
            return redirect("password_list")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, "message") else e))
            return redirect("password_create")
    folders = Folder.objects.filter(deleted_at__isnull=True)
    return render(request, "passwords/form.html", {"form_title": "Nova Senha", "folders": folders})


@login_required
def password_detail(request, pk):
    try:
        resource, secret = PasswordService.get_or_deny(request.user, pk)
    except PermissionDenied:
        return HttpResponseForbidden("Sem permissão.")
    from apps.sharing.models import Permission
    permissions = Permission.objects.filter(aco="Resource", aco_foreign_key=resource.pk)
    shared_user_ids = permissions.filter(aro="User").values_list("aro_foreign_key", flat=True)
    shared_users = User.objects.filter(pk__in=shared_user_ids)
    access_list = [{"user": resource.created_by, "permission": "Proprietário"}]
    for u in shared_users:
        if u != resource.created_by:
            perm = permissions.filter(aro_foreign_key=u.pk).first()
            perm_label = "Leitura" if perm and perm.type == Permission.READ else "Leitura/Escrita"
            access_list.append({"user": u, "permission": perm_label})
    history = resource.secrets.all().order_by("-created_at")
    return render(request, "passwords/detail.html", {
        "resource": resource, "secret": secret,
        "access_list": access_list, "secret_versions": history,
    })


@login_required
def password_edit(request, pk):
    try:
        resource, secret = PasswordService.get_or_deny(request.user, pk)
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
        return redirect("password_list")
    if request.method == "POST":
        try:
            PasswordService.update(
                request.user, pk,
                name=request.POST.get("name", "").strip(),
                username=request.POST.get("username", "").strip() or None,
                uri=request.POST.get("uri", "").strip() or None,
                description=request.POST.get("description", "").strip() or None,
                folder_id=request.POST.get("folder") or None,
                secret_data=request.POST.get("secret", ""),
            )
            messages.success(request, "Senha atualizada.")
            return redirect("password_detail", pk=pk)
        except (PermissionDenied, ValidationError) as e:
            messages.error(request, str(e))
            return redirect("password_edit", pk=pk)
    folders = Folder.objects.filter(deleted_at__isnull=True)
    return render(request, "passwords/form.html", {
        "form_title": f"Editar: {resource.name}", "resource": resource,
        "secret": secret, "folders": folders,
    })


@login_required
@require_POST
def password_delete(request, pk):
    try:
        PasswordService.delete(request.user, pk)
        messages.success(request, "Senha excluída permanentemente.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("password_list")


@login_required
@require_POST
def password_share(request, pk):
    try:
        target = PasswordService.share(
            request.user, pk,
            target_email=request.POST.get("user_email", "").strip(),
            permission_type=request.POST.get("permission", "read"),
        )
        messages.success(request, f"Senha compartilhada com {target.get_full_name() or target.email}.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, "message") else e))
    return redirect("password_detail", pk=pk)


# ── Folders ───────────────────────────────────────────────────────────────

def _user_folders(user, **extra_filters):
    qs = Folder.objects.filter(deleted_at__isnull=True, **extra_filters)
    if not user.is_staff:
        qs = qs.filter(created_by=user)
    return qs


@login_required
def folder_list(request):
    if request.method == "POST":
        try:
            FolderService.create(
                request.user,
                name=request.POST.get("name", "").strip(),
                parent_id=request.POST.get("parent") or None,
            )
            messages.success(request, "Pasta criada.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, "message") else e))
        return redirect("folder_list")
    folders = _user_folders(request.user, parent__isnull=True).prefetch_related("children")
    all_folders = _user_folders(request.user)
    return render(request, "folders/list.html", {"folders": folders, "all_folders": all_folders})


@login_required
def folder_detail(request, pk):
    folder = get_object_or_404(Folder, pk=pk, deleted_at__isnull=True)
    if not request.user.is_staff and folder.created_by != request.user:
        messages.error(request, "Sem permissão.")
        return redirect("folder_list")
    if request.method == "POST":
        try:
            FolderService.create(
                request.user,
                name=request.POST.get("name", "").strip(),
                parent_id=request.POST.get("parent") or None,
            )
            messages.success(request, "Pasta criada.")
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, "message") else e))
        return redirect("folder_detail", pk=pk)
    resources = Resource.objects.filter(folder=folder, deleted_at__isnull=True)
    user = request.user

    password_ids = set(Secret.objects.filter(user=user).values_list("resource_id", flat=True))
    file_resource_ids = set(
        FileSecret.objects.filter(user=user)
        .values_list("file_resource__resource_id", flat=True)
    )
    if user.is_staff:
        passwords = resources.filter(resource_type__slug="password")
        file_resources = FileResource.objects.filter(
            resource__folder=folder, resource__deleted_at__isnull=True, deleted_at__isnull=True,
        ).select_related("resource")
    else:
        passwords = resources.filter(pk__in=password_ids, resource_type__slug="password")
        file_resources = FileResource.objects.filter(
            resource__folder=folder, resource__deleted_at__isnull=True, deleted_at__isnull=True,
            pk__in=FileSecret.objects.filter(user=user).values_list("file_resource_id", flat=True),
        ).select_related("resource")

    children = _user_folders(user, parent=folder)
    all_folders = _user_folders(user)
    return render(request, "folders/list.html", {
        "folders": children, "current_folder": folder,
        "passwords": passwords, "file_resources": file_resources,
        "all_folders": all_folders,
    })


@login_required
@require_POST
def folder_delete(request, pk):
    try:
        FolderService.delete(request.user, pk)
        messages.success(request, "Pasta excluída permanentemente.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("folder_list")


# ── Groups ────────────────────────────────────────────────────────────────

@login_required
def group_list(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            group = Group.objects.create(name=name, created_by=request.user)
            GroupUser.objects.create(group=group, user=request.user, is_admin=True)
            messages.success(request, f'Grupo "{name}" criado.')
        else:
            messages.error(request, "Nome do grupo é obrigatório.")
        return redirect("group_list")
    groups = GroupService.list_for_user(request.user)
    return render(request, "groups/list.html", {"groups": groups})


@login_required
def group_detail(request, pk):
    try:
        group, members, available_users, is_admin = GroupService.get_detail(request.user, pk)
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
        return redirect("group_list")
    return render(request, "groups/detail.html", {
        "group": group, "members": members,
        "available_users": available_users, "shared_resources": [],
        "is_group_admin": is_admin,
    })


@login_required
def group_edit(request, pk):
    if request.method == "POST":
        try:
            GroupService.edit(request.user, pk, request.POST.get("name", ""))
            messages.success(request, "Grupo atualizado.")
        except PermissionDenied:
            messages.error(request, "Sem permissão.")
    return redirect("group_detail", pk=pk)


@login_required
@require_POST
def group_delete(request, pk):
    try:
        GroupService.delete(request.user, pk)
        messages.success(request, "Grupo excluído permanentemente.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
        return redirect("group_detail", pk=pk)
    return redirect("group_list")


@login_required
@require_POST
def group_add_member(request, pk):
    try:
        target = GroupService.add_member(
            request.user, pk,
            user_id=request.POST.get("user_id", "") or None,
            email=request.POST.get("email", "") or None,
        )
        messages.success(request, f"{target.get_full_name() or target.email} adicionado ao grupo.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, "message") else e))
    return redirect("group_detail", pk=pk)


@login_required
@require_POST
def group_remove_member(request, pk, user_pk):
    try:
        GroupService.remove_member(request.user, pk, user_pk)
        messages.success(request, "Membro removido.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("group_detail", pk=pk)


@login_required
@require_POST
def group_toggle_admin(request, pk, user_pk):
    try:
        GroupService.toggle_admin(request.user, pk, user_pk)
        messages.success(request, "Permissão atualizada.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("group_detail", pk=pk)


# ── Users (admin) ─────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff)
def user_list(request):
    users = User.objects.filter(deleted_at__isnull=True).order_by("-created_at")
    q = request.GET.get("q", "")
    if q:
        users = users.filter(email__icontains=q) | users.filter(first_name__icontains=q)
    return render(request, "users/list.html", {"users": users})


@login_required
@user_passes_test(is_staff)
def user_detail(request, pk):
    profile_user = get_object_or_404(User, pk=pk)
    gpg_keys = GpgKey.objects.filter(user=profile_user, deleted_at__isnull=True)
    logs = ActionLog.objects.filter(user=profile_user).order_by("-created_at")[:20]
    return render(request, "users/detail.html", {
        "profile_user": profile_user, "gpg_keys": gpg_keys, "logs": logs,
    })


@login_required
@user_passes_test(is_staff)
@require_POST
def user_invite(request):
    email = request.POST.get("email", "")
    first_name = request.POST.get("first_name", "")
    last_name = request.POST.get("last_name", "")
    role = request.POST.get("role", "USER")
    if User.objects.filter(email=email).exists():
        messages.error(request, "Usuário já existe.")
    else:
        import secrets
        User.objects.create_user(
            username=email.split("@")[0], email=email,
            password=secrets.token_urlsafe(16),
            first_name=first_name, last_name=last_name, role=role,
        )
        messages.success(request, f"Convite enviado para {email}.")
    return redirect("user_list")


@login_required
@user_passes_test(is_staff)
@require_POST
def user_toggle_active(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.is_active = not u.is_active
    u.is_suspended = not u.is_active
    u.save()
    messages.success(request, f"Usuário {'reativado' if u.is_active else 'suspenso'}.")
    return redirect("user_detail", pk=pk)


@login_required
@user_passes_test(is_staff)
@require_POST
def user_delete(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.hard_delete()
    messages.success(request, "Usuário excluído permanentemente.")
    return redirect("user_list")


# ── Files ─────────────────────────────────────────────────────────────────

@login_required
def file_list(request):
    accessible = FileSecret.objects.filter(user=request.user).values_list("file_resource_id", flat=True)
    files = FileResource.objects.filter(
        pk__in=accessible, upload_completed=True,
        deleted_at__isnull=True, resource__deleted_at__isnull=True,
    ).select_related("resource", "created_by").order_by("-created_at")
    category = request.GET.get("category", "")
    if category:
        files = files.filter(mime_category=category)
    q = request.GET.get("q", "")
    if q:
        files = files.filter(resource__name__icontains=q)
    return render(request, "files/list.html", {"files": files, "current_category": category})


@login_required
def file_upload(request):
    if request.method == "POST" and request.FILES.get("file"):
        try:
            fr = FileService.upload(
                request.user, request.FILES["file"],
                folder_id=request.POST.get("folder") or None,
            )
            messages.success(request, f'Arquivo "{fr.original_name_encrypted}" enviado.')
            return redirect("file_detail", pk=fr.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, "message") else e))
            return redirect("file_upload")
    folders = _user_folders(request.user)
    return render(request, "files/upload.html", {"folders": folders})


@login_required
def file_create_text(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        content = request.POST.get("content", "")
        if not name:
            messages.error(request, "Informe um nome para o arquivo.")
            return redirect("file_create_text")
        if not content:
            messages.error(request, "O conteúdo não pode estar vazio.")
            return redirect("file_create_text")
        try:
            fr = FileService.create_text(
                request.user, name, content,
                folder_id=request.POST.get("folder") or None,
            )
            messages.success(request, f'Arquivo "{fr.original_name_encrypted}" criado.')
            return redirect("file_detail", pk=fr.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, "message") else e))
            return redirect("file_create_text")
    folders = _user_folders(request.user)
    return render(request, "files/create_text.html", {"folders": folders})


@login_required
def file_detail(request, pk):
    try:
        file, secret = FileService.get_or_deny(request.user, pk)
    except PermissionDenied:
        return HttpResponseForbidden("Sem permissão.")
    access_logs = FileAccessLog.objects.filter(file_resource=file).select_related("user").order_by("-created_at")[:20]
    shared_secrets = FileSecret.objects.filter(file_resource=file).select_related("user")
    return render(request, "files/detail.html", {
        "file": file, "secret": secret,
        "access_logs": access_logs, "shared_users": shared_secrets,
    })


@login_required
def file_download(request, pk):
    try:
        content, filename = FileService.download(request.user, pk)
    except PermissionDenied:
        return HttpResponseForbidden("Sem permissão.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, "message") else e))
        return redirect("file_detail", pk=pk)
    response = HttpResponse(content, content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def file_delete(request, pk):
    try:
        FileService.delete(request.user, pk)
        messages.success(request, "Arquivo excluído permanentemente.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("file_list")


@login_required
@require_POST
def file_share(request, pk):
    try:
        target = FileService.share(request.user, pk, request.POST.get("user_query", "").strip())
        messages.success(request, f"Arquivo compartilhado com {target.get_full_name() or target.email}.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, "message") else e))
    return redirect("file_detail", pk=pk)


@login_required
@require_POST
def file_unshare(request, pk):
    try:
        FileService.unshare(request.user, pk, request.POST.get("user_id"))
        messages.success(request, "Acesso revogado.")
    except PermissionDenied:
        messages.error(request, "Sem permissão.")
    return redirect("file_detail", pk=pk)


# ── Audit ─────────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff)
def audit_logs(request):
    logs = ActionLog.objects.select_related("user").order_by("-created_at")
    action_filter = request.GET.get("action", "")
    if action_filter:
        logs = logs.filter(action=action_filter)
    user_filter = request.GET.get("user", "")
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    status_filter = request.GET.get("status", "")
    if status_filter:
        logs = logs.filter(status=status_filter.lower())
    from apps.audit.middleware import ROUTE_LABELS
    log_list = list(logs[:200])
    for log in log_list:
        log.action_label = ROUTE_LABELS.get(log.action, log.action)
    action_choices = ActionLog.objects.values_list("action", flat=True).distinct().order_by("action")
    return render(request, "audit/list.html", {
        "logs": log_list,
        "filter_users": User.objects.filter(deleted_at__isnull=True),
        "action_choices": [(a, ROUTE_LABELS.get(a, a)) for a in action_choices],
    })


# ── Profile ───────────────────────────────────────────────────────────────

@login_required
def profile(request):
    if request.method == "POST":
        request.user.first_name = request.POST.get("first_name", "").strip()
        request.user.last_name = request.POST.get("last_name", "").strip()
        request.user.locale = request.POST.get("locale", "pt-br")
        avatar = request.POST.get("avatar_url", "").strip()
        if avatar and not avatar.startswith(("http://", "https://")):
            messages.error(request, "URL do avatar deve começar com http:// ou https://.")
            return redirect("profile")
        request.user.avatar_url = avatar
        request.user.save()
        messages.success(request, "Perfil atualizado.")
        return redirect("profile")
    gpg_keys = GpgKey.objects.filter(user=request.user, deleted_at__isnull=True)
    from apps.mfa.models import BackupCode
    backup_codes = BackupCode.objects.filter(user=request.user, used=False) if request.user.totp_enabled else []
    return render(request, "profile/index.html", {
        "gpg_keys": gpg_keys, "backup_codes": backup_codes,
    })


@login_required
@require_POST
def profile_change_password(request):
    current = request.POST.get("current_password", "")
    new = request.POST.get("new_password", "")
    confirm = request.POST.get("confirm_password", "")
    if new != confirm:
        messages.error(request, "As senhas não coincidem.")
    elif not request.user.check_password(current):
        messages.error(request, "Senha atual incorreta.")
    else:
        min_len = get_config("PASSWORD_MIN_LENGTH", 12)
        try:
            min_len = int(min_len)
        except (ValueError, TypeError):
            min_len = 12
        if len(new) < min_len:
            messages.error(request, f"A nova senha deve ter no mínimo {min_len} caracteres.")
        else:
            request.user.set_password(new)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Senha alterada com sucesso.")
    return redirect("profile")


# ── MFA ───────────────────────────────────────────────────────────────────

@login_required
def mfa_setup(request):
    import pyotp
    import secrets as py_secrets
    from apps.mfa.models import TOTPDevice, BackupCode

    if request.user.totp_enabled:
        messages.info(request, "TOTP já está ativo.")
        return redirect("profile")

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        if not device:
            messages.error(request, "Inicie o setup novamente.")
            return redirect("mfa_setup")
        totp = pyotp.TOTP(device.secret_key)
        if totp.verify(code):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            BackupCode.objects.filter(user=request.user).delete()
            codes = [BackupCode(user=request.user, code=py_secrets.token_hex(5)) for _ in range(10)]
            BackupCode.objects.bulk_create(codes)
            messages.success(request, "MFA ativado com sucesso!")
            return render(request, "mfa/backup_codes.html", {"codes": [c.code for c in codes]})
        else:
            messages.error(request, "Código inválido. Tente novamente.")

    TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
    secret = pyotp.random_base32()
    TOTPDevice.objects.create(user=request.user, secret_key=secret)
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=request.user.email, issuer_name="Wisecofre")

    import qrcode, io, base64
    img = qrcode.make(provisioning_uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    return render(request, "mfa/setup.html", {
        "provisioning_uri": provisioning_uri,
        "secret": secret,
        "qr_data_uri": qr_data_uri,
    })


def mfa_verify(request):
    user_id = request.session.get("mfa_user_id")
    if not user_id:
        return redirect("login")
    error = None
    if request.method == "POST":
        import pyotp
        from django.utils import timezone
        from apps.mfa.models import TOTPDevice, BackupCode

        code = request.POST.get("code", "").strip()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return redirect("login")

        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if device and pyotp.TOTP(device.secret_key).verify(code):
            login(request, user)
            _set_session_timeout(request)
            del request.session["mfa_user_id"]
            next_url = request.session.pop("mfa_next", "dashboard")
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = "dashboard"
            return redirect(next_url)

        backup = BackupCode.objects.filter(user_id=user_id, code=code, used=False).first()
        if backup:
            backup.used = True
            backup.used_at = timezone.now()
            backup.save(update_fields=["used", "used_at"])
            login(request, user)
            _set_session_timeout(request)
            del request.session["mfa_user_id"]
            return redirect(request.session.pop("mfa_next", "dashboard"))

        error = "Código inválido."
    return render(request, "mfa/verify.html", {"error": error})


@login_required
@require_POST
def mfa_disable(request):
    from apps.mfa.models import TOTPDevice, BackupCode
    TOTPDevice.objects.filter(user=request.user).delete()
    BackupCode.objects.filter(user=request.user).delete()
    messages.success(request, "MFA desativado.")
    return redirect("profile")


@login_required
@require_POST
def gpg_key_upload(request):
    messages.info(request, "Upload de chave GPG via API /api/v1/gpg-keys/.")
    return redirect("profile")


@login_required
@require_POST
def gpg_key_delete(request, pk):
    key = get_object_or_404(GpgKey, pk=pk)
    if key.user != request.user and not request.user.is_staff:
        messages.error(request, "Sem permissão.")
    else:
        key.delete()
        messages.success(request, "Chave removida.")
    return redirect("profile")


# ── Admin Settings ────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff)
def admin_settings(request):
    from apps.sso.models import SSOProvider
    if request.method == "POST":
        action = request.POST.get("action", "save_configs")
        if action == "create_sso":
            client_id = request.POST.get("SSO_CLIENT_ID", "").strip()
            if client_id:
                SSOProvider.objects.create(
                    provider=request.POST.get("SSO_PROVIDER_TYPE", "").lower(),
                    client_id=client_id,
                    client_secret=request.POST.get("SSO_CLIENT_SECRET", ""),
                    tenant_id=request.POST.get("SSO_TENANT_ID", ""),
                    discovery_url=request.POST.get("SSO_DISCOVERY_URL", ""),
                    is_enabled=bool(request.POST.get("SSO_ENABLED")),
                )
                messages.success(request, "Provedor SSO adicionado.")
            else:
                messages.error(request, "Client ID é obrigatório.")
        else:
            for field in CONFIG_FIELDS:
                if field in CHECKBOX_FIELDS:
                    val = field in request.POST
                else:
                    val = request.POST.get(field, "")
                SystemConfiguration.objects.update_or_create(
                    key=field, defaults={"value": val, "modified_by": request.user}
                )
            messages.success(request, "Configurações salvas.")
        return redirect("admin_settings")
    configs = {}
    for c in SystemConfiguration.objects.all():
        configs[c.key] = c.value
    for key, default in CONFIG_DEFAULTS.items():
        configs.setdefault(key, default)
    sso_providers = SSOProvider.objects.all().order_by("-created_at")
    return render(request, "admin_settings/index.html", {
        "configs": configs, "sso_providers": sso_providers,
    })


@login_required
@user_passes_test(is_staff)
@require_POST
def admin_test_storage(request):
    try:
        import boto3
        from botocore.config import Config
        from django.conf import settings
        client = boto3.client(
            "s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )
        client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
        return HttpResponse('<span class="text-success"><i class="bi bi-check-circle"></i> Conexão OK</span>')
    except Exception as e:
        import logging
        logging.getLogger("wisecofre").exception("Storage test failed")
        return HttpResponse(f'<span class="text-danger"><i class="bi bi-x-circle"></i> Erro: {escape(str(e))}</span>')


@login_required
@user_passes_test(is_staff)
@require_POST
def admin_test_email(request):
    import smtplib
    host = get_config("SMTP_HOST", "")
    port = int(get_config("SMTP_PORT", 587))
    use_tls = get_config("SMTP_USE_TLS", True)
    user = get_config("SMTP_USER", "")
    password = get_config("SMTP_PASSWORD", "")
    sender = get_config("EMAIL_SENDER_ADDRESS", "")
    if not host:
        return HttpResponse('<span class="text-warning"><i class="bi bi-exclamation-circle"></i> SMTP Host não configurado</span>')
    try:
        srv = smtplib.SMTP(host, port, timeout=10)
        srv.ehlo()
        if use_tls and use_tls is not False and str(use_tls).lower() not in ("false", "0"):
            srv.starttls()
            srv.ehlo()
        if user and password:
            srv.login(user, password)
        # Send test email to the logged-in admin
        to_addr = request.user.email
        if to_addr and sender:
            from email.mime.text import MIMEText
            msg = MIMEText("Este é um email de teste do Wisecofre. Se você recebeu, a configuração SMTP está funcionando.")
            msg["Subject"] = "Wisecofre — Teste de Email"
            msg["From"] = sender
            msg["To"] = to_addr
            srv.sendmail(sender, [to_addr], msg.as_string())
            srv.quit()
            return HttpResponse(f'<span class="text-success"><i class="bi bi-check-circle"></i> Conexão OK — email enviado para {escape(to_addr)}</span>')
        srv.quit()
        return HttpResponse('<span class="text-success"><i class="bi bi-check-circle"></i> Conexão SMTP OK</span>')
    except Exception as e:
        import logging
        logging.getLogger("wisecofre").exception("Email test failed")
        return HttpResponse(f'<span class="text-danger"><i class="bi bi-x-circle"></i> Erro: {escape(str(e))}</span>')


@login_required
@user_passes_test(is_staff)
@require_POST
def admin_test_ldap(request):
    return HttpResponse(
        '<span class="text-info"><i class="bi bi-info-circle"></i> '
        'LDAP está em Beta. Configure um servidor LDAP externo para testar a conexão.</span>'
    )


@login_required
@user_passes_test(is_staff)
@require_POST
def admin_sso_delete(request, pk):
    from apps.sso.models import SSOProvider
    sso = get_object_or_404(SSOProvider, pk=pk)
    sso.hard_delete()
    messages.success(request, "Provedor SSO removido.")
    return redirect("admin_settings")


@login_required
@user_passes_test(is_staff)
def audit_export_csv(request):
    import csv
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(["Data", "Usuário", "Ação", "Status", "IP"])
    for log in ActionLog.objects.select_related("user").order_by("-created_at")[:1000]:
        writer.writerow([
            log.created_at.isoformat(),
            log.user.email if log.user else "-",
            log.action, log.status, log.ip_address,
        ])
    return response
