from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .filters import ResourceFilter
from .models import Favorite, Resource, ResourceType, Secret, Tag
from .serializers import (
    FavoriteSerializer,
    ResourceCreateSerializer,
    ResourceSerializer,
    ResourceTypeSerializer,
    SecretHistorySerializer,
    SecretSerializer,
    TagSerializer,
)


class ResourceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_class = ResourceFilter
    ordering_fields = ["name", "created_at", "modified_at", "expired_at"]
    search_fields = ["name", "username", "uri", "description"]

    def get_queryset(self):
        return (
            Resource.objects.select_related("resource_type", "created_by", "folder")
            .prefetch_related("tags", "favorites")
            .filter(
                # owner OR shared with me
                models.Q(created_by=self.request.user)
                | models.Q(
                    id__in=self._shared_resource_ids(),
                )
            )
        )

    def _shared_resource_ids(self):
        from apps.sharing.models import Permission

        return Permission.objects.filter(
            aco="Resource",
            aro="User",
            aro_foreign_key=self.request.user.pk,
        ).values_list("aco_foreign_key", flat=True)

    def get_serializer_class(self):
        if self.action == "create":
            return ResourceCreateSerializer
        return ResourceSerializer

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)

    # --- custom actions ---

    @action(detail=True, methods=["get", "put"])
    def secrets(self, request, pk=None):
        resource = self.get_object()
        if request.method == "GET":
            secrets = Secret.objects.filter(resource=resource, user=request.user)
            return Response(SecretSerializer(secrets, many=True).data)
        # PUT
        secret, created = Secret.objects.get_or_create(
            resource=resource,
            user=request.user,
            defaults={"data": request.data.get("data", "")},
        )
        if not created:
            from .models import SecretHistory

            SecretHistory.objects.create(
                secret=secret, data=secret.data, created_by=request.user
            )
            secret.data = request.data.get("data", "")
            secret.save(update_fields=["data", "modified_at"])
        return Response(SecretSerializer(secret).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        resource = self.get_object()
        secret = Secret.objects.filter(resource=resource, user=request.user).first()
        if not secret:
            return Response([])
        entries = secret.history.order_by("-created_at")
        return Response(SecretHistorySerializer(entries, many=True).data)

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        resource = self.get_object()
        fav, created = Favorite.objects.get_or_create(
            user=request.user, resource=resource
        )
        if not created:
            return Response(
                {"detail": "Já está nos favoritos."}, status=status.HTTP_200_OK
            )
        return Response(
            FavoriteSerializer(fav).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def unfavorite(self, request, pk=None):
        resource = self.get_object()
        deleted = Favorite.objects.filter(
            user=request.user, resource=resource
        ).delete()
        if deleted[0]:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"detail": "Não estava nos favoritos."}, status=status.HTTP_404_NOT_FOUND
        )


class ResourceTypeViewSet(ReadOnlyModelViewSet):
    queryset = ResourceType.objects.all()
    serializer_class = ResourceTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class TagViewSet(ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Tag.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
