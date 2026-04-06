from django.contrib import admin

from .models import SSOProvider


@admin.register(SSOProvider)
class SSOProviderAdmin(admin.ModelAdmin):
    list_display = ["provider", "is_enabled", "allow_registration", "created_at"]
    list_filter = ["provider", "is_enabled"]
