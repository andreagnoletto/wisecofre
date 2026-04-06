from django.contrib import admin

from .models import ActionLog


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ["action", "user", "status", "ip_address", "created_at"]
    list_filter = ["status", "action", "created_at"]
    search_fields = ["action", "user__email", "ip_address"]
    readonly_fields = [
        "id",
        "user",
        "action",
        "context",
        "status",
        "ip_address",
        "user_agent",
        "created_at",
    ]
    ordering = ["-created_at"]
