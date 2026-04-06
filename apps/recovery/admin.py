from django.contrib import admin

from .models import AccountRecoveryOrganizationKey, AccountRecoveryRequest


@admin.register(AccountRecoveryOrganizationKey)
class AccountRecoveryOrganizationKeyAdmin(admin.ModelAdmin):
    list_display = ["fingerprint", "created_by", "created_at"]
    search_fields = ["fingerprint"]


@admin.register(AccountRecoveryRequest)
class AccountRecoveryRequestAdmin(admin.ModelAdmin):
    list_display = ["requester", "status", "reviewer", "expires_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["requester__email", "token"]
    readonly_fields = ["token"]
