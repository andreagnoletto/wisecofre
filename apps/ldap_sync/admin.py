from django.contrib import admin

from .models import LDAPConfiguration


@admin.register(LDAPConfiguration)
class LDAPConfigurationAdmin(admin.ModelAdmin):
    list_display = ["host", "port", "use_tls", "is_enabled", "sync_interval_minutes"]
    list_filter = ["is_enabled", "use_tls"]
