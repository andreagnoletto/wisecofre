from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User

from .models import FileAccessLog, FileResource
from .permissions import HasFileAccess
from .serializers import (
    FileAccessLogSerializer,
    FileConfirmSerializer,
    FileResourceSerializer,
    FileSecretSerializer,
    FileShareSerializer,
    FileUploadInitSerializer,
)
from .services import FileService


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "0.0.0.0")


class FileViewSet(ModelViewSet):
    serializer_class = FileResourceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.file_service = FileService()

    def get_queryset(self):
        return (
            FileResource.objects.filter(secrets__user=self.request.user)
            .select_related("resource")
            .distinct()
        )

    def get_permissions(self):
        if self.action in ("retrieve", "destroy", "download_url", "secret", "share", "logs"):
            return [IsAuthenticated(), HasFileAccess()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        file_resource = self.get_object()
        ip = _get_client_ip(request)
        try:
            self.file_service.delete_file(file_resource, request.user, ip_address=ip)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="upload-url")
    def upload_url(self, request):
        serializer = FileUploadInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            file_resource, presigned_url = self.file_service.initiate_upload(
                user=request.user,
                resource_data={"name": data["name"], "folder_id": data.get("folder_id")},
                checksum_sha256=data["checksum_sha256"],
                size_bytes=data["size_bytes"],
                original_name_encrypted=data["original_name_encrypted"],
                session_key_encrypted=data["session_key_encrypted"],
                mime_category=data.get("mime_category", "other"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "file_resource": FileResourceSerializer(file_resource).data,
                "upload_url": presigned_url,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="confirm-upload")
    def confirm_upload(self, request, pk=None):
        file_resource = self.get_object()
        try:
            file_resource = self.file_service.confirm_upload(file_resource)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FileResourceSerializer(file_resource).data)

    @action(detail=True, methods=["get"], url_path="download-url")
    def download_url(self, request, pk=None):
        file_resource = self.get_object()
        ip = _get_client_ip(request)
        try:
            url = self.file_service.get_download_url(file_resource, request.user, ip_address=ip)
        except (PermissionError, ValueError) as e:
            code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionError) else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(e)}, status=code)
        return Response({"download_url": url})

    @action(detail=True, methods=["get"])
    def secret(self, request, pk=None):
        file_resource = self.get_object()
        secret = file_resource.secrets.filter(user=request.user).first()
        if not secret:
            return Response({"detail": "Sem acesso."}, status=status.HTTP_403_FORBIDDEN)
        return Response(FileSecretSerializer(secret).data)

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        file_resource = self.get_object()
        serializer = FileShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = _get_client_ip(request)
        errors = []
        for recipient in serializer.validated_data["recipients"]:
            try:
                to_user = User.objects.get(id=recipient["user_id"])
                self.file_service.share_file(
                    file_resource=file_resource,
                    from_user=request.user,
                    to_user=to_user,
                    session_key_encrypted_for_recipient=recipient["session_key_encrypted"],
                    permission_type=recipient.get("permission_type", 1),
                    ip_address=ip,
                )
            except (User.DoesNotExist, PermissionError) as e:
                errors.append({"user_id": str(recipient["user_id"]), "error": str(e)})
        if errors:
            return Response({"shared": True, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response({"shared": True})

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        file_resource = self.get_object()
        if file_resource.created_by != request.user and not request.user.is_admin:
            return Response({"detail": "Apenas o criador ou admin pode ver logs."}, status=status.HTTP_403_FORBIDDEN)
        logs = FileAccessLog.objects.filter(file_resource=file_resource).order_by("-created_at")
        serializer = FileAccessLogSerializer(logs, many=True)
        return Response(serializer.data)
