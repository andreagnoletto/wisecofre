from django_filters import rest_framework as filters
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import GenericViewSet

from .models import ActionLog
from .serializers import ActionLogSerializer


class ActionLogFilter(filters.FilterSet):
    user_id = filters.UUIDFilter(field_name="user_id")
    action = filters.CharFilter(lookup_expr="icontains")
    date_from = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = ActionLog
        fields = ["user_id", "action", "status", "date_from", "date_to"]


class ActionLogViewSet(ListModelMixin, GenericViewSet):
    queryset = ActionLog.objects.select_related("user").all()
    serializer_class = ActionLogSerializer
    permission_classes = [IsAdminUser]
    filterset_class = ActionLogFilter
    ordering_fields = ["created_at", "action", "status"]
