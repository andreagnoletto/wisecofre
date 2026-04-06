from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin, ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ViewSet

from .models import Permission
from .serializers import PermissionSerializer, ShareResourceSerializer


class ShareViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="resource/(?P<resource_id>[^/.]+)")
    def share_resource(self, request, resource_id=None):
        serializer = ShareResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.resources.models import Resource, Secret

        resource = Resource.objects.get(pk=resource_id)
        created = []
        for recipient in serializer.validated_data["recipients"]:
            perm, was_created = Permission.objects.get_or_create(
                aco="Resource",
                aco_foreign_key=resource.pk,
                aro="User",
                aro_foreign_key=recipient["user_id"],
                defaults={
                    "type": recipient.get("permission_type", Permission.READ),
                    "created_by": request.user,
                },
            )
            secret_data = recipient.get("secret_data")
            if secret_data:
                Secret.objects.update_or_create(
                    resource=resource,
                    user_id=recipient["user_id"],
                    defaults={"data": secret_data},
                )
            if was_created:
                created.append(str(perm.pk))

        return Response({"shared": len(created)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="folder/(?P<folder_id>[^/.]+)")
    def share_folder(self, request, folder_id=None):
        from apps.folders.models import Folder

        folder = Folder.objects.get(pk=folder_id)
        recipients = request.data.get("recipients", [])
        created = []
        for r in recipients:
            perm, was_created = Permission.objects.get_or_create(
                aco="Folder",
                aco_foreign_key=folder.pk,
                aro=r.get("aro", "User"),
                aro_foreign_key=r["user_id"],
                defaults={
                    "type": r.get("permission_type", Permission.READ),
                    "created_by": request.user,
                },
            )
            if was_created:
                created.append(str(perm.pk))

        return Response({"shared": len(created)}, status=status.HTTP_201_CREATED)


class PermissionViewSet(ListModelMixin, DestroyModelMixin, GenericViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Permission.objects.all()
        aco = self.request.query_params.get("aco")
        aco_id = self.request.query_params.get("aco_foreign_key")
        if aco and aco_id:
            qs = qs.filter(aco=aco, aco_foreign_key=aco_id)
        return qs.filter(
            # only permissions the user created or that target them
            models.Q(created_by=self.request.user)
            | models.Q(aro="User", aro_foreign_key=self.request.user.pk)
        )
