from rest_framework import serializers

from .models import Folder


class FolderSerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()
    resource_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "parent",
            "created_by",
            "personal",
            "children_count",
            "resource_count",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "modified_at"]

    def get_children_count(self, obj):
        return obj.children.count()

    def get_resource_count(self, obj):
        return obj.resources.count()
