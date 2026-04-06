from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import AccountRecoveryOrganizationKey, AccountRecoveryRequest
from .serializers import OrganizationKeySerializer, RecoveryRequestSerializer


class RecoveryRequestViewSet(ModelViewSet):
    serializer_class = RecoveryRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return AccountRecoveryRequest.objects.all()
        return AccountRecoveryRequest.objects.filter(requester=self.request.user)

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class OrganizationKeyViewSet(ModelViewSet):
    queryset = AccountRecoveryOrganizationKey.objects.all()
    serializer_class = OrganizationKeySerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
