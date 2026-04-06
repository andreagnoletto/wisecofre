from django.contrib import admin

from .models import Folder


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "created_by", "personal", "created_at"]
    list_filter = ["personal", "created_at"]
    search_fields = ["name"]
    raw_id_fields = ["parent", "created_by"]
