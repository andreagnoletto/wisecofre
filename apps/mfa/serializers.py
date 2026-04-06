from rest_framework import serializers

from .models import BackupCode


class TOTPSetupSerializer(serializers.Serializer):
    provisioning_uri = serializers.CharField(read_only=True)
    qr_code = serializers.CharField(read_only=True)


class TOTPVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)


class BackupCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupCode
        fields = ["id", "code", "used", "used_at"]
        read_only_fields = fields
