from rest_framework import serializers

from .models import Group, GroupUser


class GroupUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupUser
        fields = ["id", "group", "user", "is_admin", "created_at"]
        read_only_fields = ["id", "created_at"]


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "created_by", "member_count", "created_at", "modified_at"]
        read_only_fields = ["id", "created_by", "created_at", "modified_at"]

    def get_member_count(self, obj):
        return obj.members.count()
