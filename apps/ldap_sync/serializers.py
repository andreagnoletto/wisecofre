from rest_framework import serializers

from .models import LDAPConfiguration


class LDAPConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LDAPConfiguration
        fields = [
            "id",
            "host",
            "port",
            "use_tls",
            "bind_dn",
            "bind_password",
            "base_dn",
            "user_filter",
            "group_filter",
            "sync_interval_minutes",
            "is_enabled",
            "created_at",
            "modified_at",
        ]
        extra_kwargs = {"bind_password": {"write_only": True}}
