from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

from .models import ActionLog

# GET routes that are pure navigation (no sensitive data) — skip these
SKIP_GET = frozenset({
    "dashboard", "login", "password_list", "password_create",
    "folder_list", "group_list", "group_detail", "file_list",
    "file_upload", "user_list", "audit_logs", "admin_settings",
    "profile", "schema", "swagger-ui", "mfa_setup",
})

ROUTE_LABELS = {
    "login": "Login",
    "logout": "Logout",
    "password_create": "Criar senha",
    "password_detail": "Visualizar senha",
    "password_edit": "Editar senha",
    "password_delete": "Excluir senha",
    "password_share": "Compartilhar senha",
    "folder_list": "Criar pasta",
    "folder_detail": "Acessar pasta",
    "folder_delete": "Excluir pasta",
    "group_list": "Criar grupo",
    "group_edit": "Editar grupo",
    "group_delete": "Excluir grupo",
    "group_add_member": "Adicionar membro",
    "group_remove_member": "Remover membro",
    "group_toggle_admin": "Alterar admin",
    "file_upload": "Upload arquivo",
    "file_detail": "Visualizar arquivo",
    "file_download": "Download arquivo",
    "file_delete": "Excluir arquivo",
    "file_share": "Compartilhar arquivo",
    "file_unshare": "Revogar acesso arquivo",
    "user_invite": "Convidar usuário",
    "user_detail": "Visualizar usuário",
    "user_toggle_active": "Alternar status usuário",
    "user_delete": "Excluir usuário",
    "profile": "Atualizar perfil",
    "profile_change_password": "Alterar senha própria",
    "mfa_setup": "Configurar MFA",
    "mfa_disable": "Desativar MFA",
    "gpg_key_upload": "Upload chave GPG",
    "gpg_key_delete": "Excluir chave GPG",
    "admin_settings": "Alterar configurações",
    "admin_sso_delete": "Excluir provedor SSO",
    "admin_test_storage": "Testar storage",
    "admin_test_ldap": "Testar LDAP",
    "audit_export_csv": "Exportar auditoria CSV",
}


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "0.0.0.0")


class AuditMiddleware(MiddlewareMixin):
    """Logs all state-changing requests (POST/PUT/PATCH/DELETE) and sensitive GET reads."""

    def process_response(self, request, response):
        try:
            match = resolve(request.path)
        except Exception:
            return response

        route_name = match.url_name
        if not route_name:
            return response

        # Always log POST, PUT, PATCH, DELETE
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            should_log = True
        elif request.method == "GET":
            # Log GET except pure navigation pages
            should_log = route_name not in SKIP_GET
        else:
            should_log = False

        if not should_log:
            return response

        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        is_success = 200 <= response.status_code < 400

        context = {}
        if match.kwargs:
            context["params"] = {k: str(v) for k, v in match.kwargs.items()}

        try:
            ActionLog.objects.create(
                user=user,
                action=route_name,
                status="success" if is_success else "fail",
                ip_address=_get_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                context=context,
            )
        except Exception:
            pass

        return response
