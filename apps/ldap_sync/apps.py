from django.apps import AppConfig


class LdapSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ldap_sync"
    verbose_name = "LDAP Sync"
