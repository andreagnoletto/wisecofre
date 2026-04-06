from rest_framework import serializers

from .models import AccountRecoveryOrganizationKey, AccountRecoveryRequest


class OrganizationKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountRecoveryOrganizationKey
        fields = [
            "id",
            "armored_key",
            "fingerprint",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class RecoveryRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountRecoveryRequest
        fields = [
            "id",
            "requester",
            "status",
            "token",
            "reviewer",
            "reviewed_at",
            "expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "requester",
            "status",
            "token",
            "reviewer",
            "reviewed_at",
            "created_at",
        ]
