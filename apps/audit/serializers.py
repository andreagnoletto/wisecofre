from rest_framework import serializers

from .models import ActionLog


class ActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionLog
        fields = [
            "id",
            "user",
            "action",
            "context",
            "status",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields
