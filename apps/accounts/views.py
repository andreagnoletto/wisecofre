from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import GpgKey, User
from .permissions import IsAdmin, IsOwnerOrAdmin
from .serializers import GpgKeySerializer, UserCreateSerializer, UserMeSerializer, UserSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.select_related().all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "me":
            return UserMeSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.is_suspended = True
        user.save(update_fields=["is_suspended"])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        user = self.get_object()
        user.is_suspended = False
        user.save(update_fields=["is_suspended"])
        return Response(UserSerializer(user).data)

    @action(detail=False, methods=["get", "put"], permission_classes=[IsAuthenticated])
    def me(self, request):
        if request.method == "GET":
            return Response(UserMeSerializer(request.user).data)
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GpgKeyViewSet(ModelViewSet):
    serializer_class = GpgKeySerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        return GpgKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
