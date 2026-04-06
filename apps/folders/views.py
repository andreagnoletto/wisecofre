from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Folder
from .serializers import FolderSerializer


class FolderViewSet(ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Folder.objects.filter(created_by=self.request.user).select_related(
            "parent"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        folder = self.get_object()
        from apps.sharing.models import Permission

        recipients = request.data.get("recipients", [])
        created = []
        for r in recipients:
            perm, was_created = Permission.objects.get_or_create(
                aco="Folder",
                aco_foreign_key=folder.pk,
                aro=r.get("aro", "User"),
                aro_foreign_key=r["aro_foreign_key"],
                defaults={
                    "type": r.get("type", 1),
                    "created_by": request.user,
                },
            )
            if was_created:
                created.append(str(perm.pk))
        return Response({"shared": len(created)})

    @action(detail=True, methods=["get"])
    def resources(self, request, pk=None):
        folder = self.get_object()
        from apps.resources.serializers import ResourceSerializer

        qs = folder.resources.all()
        serializer = ResourceSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)
