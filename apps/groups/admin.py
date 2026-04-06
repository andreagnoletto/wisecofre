from django.contrib import admin

from .models import Group, GroupUser


class GroupUserInline(admin.TabularInline):
    model = GroupUser
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at"]
    search_fields = ["name"]
    raw_id_fields = ["created_by"]
    inlines = [GroupUserInline]


@admin.register(GroupUser)
class GroupUserAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "is_admin", "created_at"]
    list_filter = ["is_admin"]
    raw_id_fields = ["group", "user"]
