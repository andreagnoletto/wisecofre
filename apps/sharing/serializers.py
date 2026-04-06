from rest_framework import serializers

from .models import Permission


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = [
            "id",
            "aco",
            "aco_foreign_key",
            "aro",
            "aro_foreign_key",
            "type",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class RecipientSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    secret_data = serializers.CharField(required=False, allow_blank=True)
    permission_type = serializers.IntegerField(default=Permission.READ)


class ShareResourceSerializer(serializers.Serializer):
    recipients = RecipientSerializer(many=True)
