from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import GpgKey, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "role", "is_suspended", "is_staff", "created_at")
    list_filter = ("role", "is_suspended", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-created_at",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("WiseCofre", {"fields": ("role", "is_suspended", "avatar_url", "locale")}),
    )


@admin.register(GpgKey)
class GpgKeyAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "user", "key_type", "bits", "expires_at", "created_at")
    search_fields = ("fingerprint", "uid", "user__email")
    list_filter = ("key_type",)
    readonly_fields = ("id", "created_at", "modified_at")
