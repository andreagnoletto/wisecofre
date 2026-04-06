from rest_framework import serializers

from .models import (
    Favorite,
    Resource,
    ResourceTag,
    ResourceType,
    Secret,
    SecretHistory,
    Tag,
)


class ResourceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        fields = ["id", "name", "slug", "description"]
        read_only_fields = ["id"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "slug", "label", "color", "created_at"]
        read_only_fields = ["id", "created_at"]


class SecretSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secret
        fields = ["id", "resource", "user", "data"]
        read_only_fields = ["id", "resource", "user"]


class SecretHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SecretHistory
        fields = ["id", "data", "created_by", "created_at"]
        read_only_fields = fields


class ResourceSerializer(serializers.ModelSerializer):
    resource_type = ResourceTypeSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_favorite = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "name",
            "username",
            "uri",
            "uris",
            "description",
            "resource_type",
            "created_by",
            "modified_by",
            "folder",
            "expired_at",
            "icon",
            "tags",
            "is_favorite",
            "is_owner",
            "created_at",
            "modified_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
        ]

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.favorites.filter(user=request.user).exists()

    def get_is_owner(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.pk


class ResourceCreateSerializer(serializers.ModelSerializer):
    folder_id = serializers.UUIDField(required=False, allow_null=True)
    resource_type_id = serializers.UUIDField(source="resource_type.id", required=True)
    secret_data = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Resource
        fields = [
            "name",
            "username",
            "uri",
            "uris",
            "description",
            "resource_type_id",
            "folder_id",
            "icon",
            "expired_at",
            "secret_data",
        ]

    def validate_resource_type_id(self, value):
        if not ResourceType.objects.filter(id=value).exists():
            raise serializers.ValidationError("Tipo de recurso não encontrado.")
        return value

    def create(self, validated_data):
        resource_type_data = validated_data.pop("resource_type")
        secret_data = validated_data.pop("secret_data", None)
        folder_id = validated_data.pop("folder_id", None)
        user = self.context["request"].user

        resource = Resource.objects.create(
            **validated_data,
            resource_type_id=resource_type_data["id"],
            folder_id=folder_id,
            created_by=user,
        )

        if secret_data:
            Secret.objects.create(resource=resource, user=user, data=secret_data)

        return resource


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ["id", "user", "resource", "created_at"]
        read_only_fields = ["id", "user", "created_at"]
