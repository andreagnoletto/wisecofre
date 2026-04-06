from django.contrib import admin

from .models import BackupCode, TOTPDevice


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "confirmed", "created_at"]
    list_filter = ["confirmed"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "secret_key", "created_at"]


@admin.register(BackupCode)
class BackupCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "used", "used_at", "created_at"]
    list_filter = ["used"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "code", "created_at"]
