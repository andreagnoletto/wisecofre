from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from .models import LDAPConfiguration
from .serializers import LDAPConfigurationSerializer


class LDAPConfigurationViewSet(ModelViewSet):
    queryset = LDAPConfiguration.objects.all()
    serializer_class = LDAPConfigurationSerializer
    permission_classes = [IsAdminUser]
