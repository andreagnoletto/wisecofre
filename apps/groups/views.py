from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Group, GroupUser
from .serializers import GroupSerializer, GroupUserSerializer


class GroupViewSet(ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Group.objects.filter(
            members__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        GroupUser.objects.create(group=group, user=self.request.user, is_admin=True)

    @action(detail=True, methods=["get", "post", "delete"])
    def users(self, request, pk=None):
        group = self.get_object()

        if request.method == "GET":
            members = GroupUser.objects.filter(group=group).select_related("user")
            return Response(GroupUserSerializer(members, many=True).data)

        if request.method == "POST":
            user_id = request.data.get("user_id")
            is_admin = request.data.get("is_admin", False)
            membership, created = GroupUser.objects.get_or_create(
                group=group,
                user_id=user_id,
                defaults={"is_admin": is_admin},
            )
            if not created:
                return Response(
                    {"detail": "Usuário já é membro do grupo."},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                GroupUserSerializer(membership).data, status=status.HTTP_201_CREATED
            )

        # DELETE
        user_id = request.data.get("user_id")
        deleted, _ = GroupUser.objects.filter(group=group, user_id=user_id).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"detail": "Membro não encontrado."}, status=status.HTTP_404_NOT_FOUND
        )
