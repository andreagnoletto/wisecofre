from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from .models import SSOProvider
from .serializers import SSOProviderSerializer


class SSOProviderViewSet(ModelViewSet):
    queryset = SSOProvider.objects.all()
    serializer_class = SSOProviderSerializer
    permission_classes = [IsAdminUser]
