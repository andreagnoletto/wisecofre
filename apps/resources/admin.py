from django.contrib import admin

from .models import Resource, ResourceType, Secret, Tag


@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["label", "slug", "color", "created_by", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["label", "slug"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["name", "resource_type", "created_by", "folder", "created_at"]
    list_filter = ["resource_type", "created_at"]
    search_fields = ["name", "username", "uri"]
    raw_id_fields = ["created_by", "modified_by", "folder"]


@admin.register(Secret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ["resource", "user", "created_at"]
    raw_id_fields = ["resource", "user"]
