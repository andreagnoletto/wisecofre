from rest_framework import serializers

from .models import GpgKey, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "is_suspended",
            "avatar_url",
            "locale",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_at", "modified_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role"]


class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "locale", "avatar_url", "role", "created_at"]
        read_only_fields = ["id", "email", "role", "created_at"]


class GpgKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = GpgKey
        fields = [
            "id",
            "user",
            "armored_key",
            "fingerprint",
            "bits",
            "key_type",
            "uid",
            "expires_at",
            "created_at",
        ]
        read_only_fields = ["id", "user", "fingerprint", "bits", "key_type", "uid", "expires_at", "created_at"]
