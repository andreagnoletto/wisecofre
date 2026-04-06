from django.contrib import admin

from .models import SystemConfiguration


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ("key", "encrypted", "modified_by", "created_at", "modified_at")
    search_fields = ("key", "description")
    list_filter = ("encrypted",)
    readonly_fields = ("id", "created_at", "modified_at")
