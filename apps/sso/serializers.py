from rest_framework import serializers

from .models import SSOProvider


class SSOProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SSOProvider
        fields = [
            "id",
            "provider",
            "client_id",
            "client_secret",
            "tenant_id",
            "discovery_url",
            "is_enabled",
            "allow_registration",
            "created_at",
            "modified_at",
        ]
        extra_kwargs = {"client_secret": {"write_only": True}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.client_secret:
            data["client_secret_set"] = True
        return data
