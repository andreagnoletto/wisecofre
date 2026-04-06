from django.contrib import admin

from .models import FileAccessLog, FileResource, FileSecret


@admin.register(FileResource)
class FileResourceAdmin(admin.ModelAdmin):
    list_display = ["id", "storage_key", "mime_category", "size_bytes", "upload_completed", "created_by", "created_at"]
    list_filter = ["mime_category", "upload_completed", "encryption_version"]
    search_fields = ["storage_key", "checksum_sha256"]
    readonly_fields = ["id", "created_at", "modified_at"]
    ordering = ["-created_at"]


@admin.register(FileSecret)
class FileSecretAdmin(admin.ModelAdmin):
    list_display = ["id", "file_resource", "user", "created_at"]
    search_fields = ["user__email", "file_resource__storage_key"]
    readonly_fields = ["id", "created_at", "modified_at"]
    ordering = ["-created_at"]


@admin.register(FileAccessLog)
class FileAccessLogAdmin(admin.ModelAdmin):
    list_display = ["id", "file_resource", "user", "action", "ip_address", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["user__email", "ip_address"]
    readonly_fields = ["id", "file_resource", "user", "action", "ip_address", "user_agent", "presigned_url_expires_at", "shared_with", "created_at"]
    ordering = ["-created_at"]
