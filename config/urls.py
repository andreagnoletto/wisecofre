from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views_web import (
    admin_settings,
    admin_sso_delete,
    admin_test_ldap,
    admin_test_storage,
    audit_export_csv,
    audit_logs,
    dashboard,
    file_delete,
    file_detail,
    file_download,
    file_list,
    file_share,
    file_unshare,
    file_upload,
    file_create_text,
    folder_delete,
    folder_detail,
    folder_list,
    gpg_key_delete,
    gpg_key_upload,
    group_add_member,
    group_delete,
    group_detail,
    group_edit,
    group_list,
    group_remove_member,
    group_toggle_admin,
    login_view,
    logout_view,
    mfa_disable,
    mfa_setup,
    mfa_verify,
    password_create,
    password_delete,
    password_detail,
    password_edit,
    password_list,
    password_share,
    profile,
    profile_change_password,
    user_delete,
    user_detail,
    user_invite,
    user_list,
    user_toggle_active,
)

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # ── Dashboard ─────────────────────────────────────────────────────────
    path("", dashboard, name="dashboard"),

    # ── Passwords ─────────────────────────────────────────────────────────
    path("passwords/", password_list, name="password_list"),
    path("passwords/new/", password_create, name="password_create"),
    path("passwords/<uuid:pk>/", password_detail, name="password_detail"),
    path("passwords/<uuid:pk>/edit/", password_edit, name="password_edit"),
    path("passwords/<uuid:pk>/delete/", password_delete, name="password_delete"),
    path("passwords/<uuid:pk>/share/", password_share, name="password_share"),

    # ── Folders ───────────────────────────────────────────────────────────
    path("folders/", folder_list, name="folder_list"),
    path("folders/<uuid:pk>/", folder_detail, name="folder_detail"),
    path("folders/<uuid:pk>/delete/", folder_delete, name="folder_delete"),

    # ── Groups ────────────────────────────────────────────────────────────
    path("groups/", group_list, name="group_list"),
    path("groups/<uuid:pk>/", group_detail, name="group_detail"),
    path("groups/<uuid:pk>/edit/", group_edit, name="group_edit"),
    path("groups/<uuid:pk>/delete/", group_delete, name="group_delete"),
    path("groups/<uuid:pk>/add-member/", group_add_member, name="group_add_member"),
    path("groups/<uuid:pk>/remove-member/<uuid:user_pk>/", group_remove_member, name="group_remove_member"),
    path("groups/<uuid:pk>/toggle-admin/<uuid:user_pk>/", group_toggle_admin, name="group_toggle_admin"),

    # ── Users (admin) ─────────────────────────────────────────────────────
    path("users/", user_list, name="user_list"),
    path("users/invite/", user_invite, name="user_invite"),
    path("users/<uuid:pk>/", user_detail, name="user_detail"),
    path("users/<uuid:pk>/toggle-active/", user_toggle_active, name="user_toggle_active"),
    path("users/<uuid:pk>/delete/", user_delete, name="user_delete"),

    # ── Files ─────────────────────────────────────────────────────────────
    path("files/", file_list, name="file_list"),
    path("files/upload/", file_upload, name="file_upload"),
    path("files/new/", file_create_text, name="file_create_text"),
    path("files/<uuid:pk>/", file_detail, name="file_detail"),
    path("files/<uuid:pk>/download/", file_download, name="file_download"),
    path("files/<uuid:pk>/delete/", file_delete, name="file_delete"),
    path("files/<uuid:pk>/share/", file_share, name="file_share"),
    path("files/<uuid:pk>/unshare/", file_unshare, name="file_unshare"),

    # ── Audit ─────────────────────────────────────────────────────────────
    path("audit/", audit_logs, name="audit_logs"),
    path("audit/export/", audit_export_csv, name="audit_export_csv"),

    # ── Profile ───────────────────────────────────────────────────────────
    path("profile/", profile, name="profile"),
    path("profile/change-password/", profile_change_password, name="profile_change_password"),
    path("profile/mfa/setup/", mfa_setup, name="mfa_setup"),
    path("profile/mfa/verify/", mfa_verify, name="mfa_verify"),
    path("profile/mfa/disable/", mfa_disable, name="mfa_disable"),
    path("profile/gpg-keys/upload/", gpg_key_upload, name="gpg_key_upload"),
    path("profile/gpg-keys/<uuid:pk>/delete/", gpg_key_delete, name="gpg_key_delete"),

    # ── Admin settings ────────────────────────────────────────────────────
    path("settings/", admin_settings, name="admin_settings"),
    path("settings/test-storage/", admin_test_storage, name="admin_test_storage"),
    path("settings/test-ldap/", admin_test_ldap, name="admin_test_ldap"),
    path("settings/sso/<uuid:pk>/delete/", admin_sso_delete, name="admin_sso_delete"),

    # ── Django Admin ──────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── API ───────────────────────────────────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.resources.urls")),
    path("api/v1/", include("apps.folders.urls")),
    path("api/v1/", include("apps.groups.urls")),
    path("api/v1/share/", include("apps.sharing.urls_share")),
    path("api/v1/permissions/", include("apps.sharing.urls_permissions")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/mfa/", include("apps.mfa.urls")),
    path("api/v1/", include("apps.files.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.sso.urls")),
    path("api/v1/", include("apps.ldap_sync.urls")),
    path("api/v1/", include("apps.recovery.urls")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns = [path("__debug__/", include("debug_toolbar.urls"))] + urlpatterns

if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
