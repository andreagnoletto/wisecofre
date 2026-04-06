from django.contrib import admin

from .models import Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["aco", "aco_foreign_key", "aro", "aro_foreign_key", "type", "created_at"]
    list_filter = ["aco", "aro", "type"]
    search_fields = ["aco_foreign_key", "aro_foreign_key"]
