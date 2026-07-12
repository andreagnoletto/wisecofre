from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
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

        resource = get_object_or_404(Resource, pk=resource_id, deleted_at__isnull=True)
        # Autorização: só quem tem o segredo do recurso (ou staff) pode compartilhar.
        owner_secret = Secret.objects.filter(resource=resource, user=request.user).first()
        if not owner_secret and not request.user.is_staff:
            raise PermissionDenied("Sem permissão para compartilhar este recurso.")

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
            # O segredo do destinatário vem do compartilhador — NUNCA de dado
            # arbitrário do request (isso permitia sobrescrever o segredo alheio).
            if owner_secret:
                Secret.objects.update_or_create(
                    resource=resource,
                    user_id=recipient["user_id"],
                    defaults={"data": owner_secret.data},
                )
            if was_created:
                created.append(str(perm.pk))

        return Response({"shared": len(created)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="folder/(?P<folder_id>[^/.]+)")
    def share_folder(self, request, folder_id=None):
        from apps.folders.models import Folder

        folder = get_object_or_404(Folder, pk=folder_id, deleted_at__isnull=True)
        # Autorização: só o dono da pasta (ou staff) pode compartilhá-la.
        if folder.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("Sem permissão para compartilhar esta pasta.")

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
