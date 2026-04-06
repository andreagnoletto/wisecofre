from django.utils import timezone
from django_filters import rest_framework as filters

from .models import Resource


class ResourceFilter(filters.FilterSet):
    search = filters.CharFilter(method="filter_search")
    folder_id = filters.UUIDFilter(field_name="folder_id")
    tag = filters.CharFilter(method="filter_tag")
    favorite = filters.BooleanFilter(method="filter_favorite")
    expired = filters.BooleanFilter(method="filter_expired")
    shared_with_me = filters.BooleanFilter(method="filter_shared_with_me")
    owned_by_me = filters.BooleanFilter(method="filter_owned_by_me")
    resource_type = filters.CharFilter(field_name="resource_type__slug")

    class Meta:
        model = Resource
        fields = [
            "folder_id",
            "resource_type",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)

    def filter_tag(self, queryset, name, value):
        return queryset.filter(tags__slug=value)

    def filter_favorite(self, queryset, name, value):
        if value:
            return queryset.filter(favorites__user=self.request.user)
        return queryset

    def filter_expired(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(expired_at__lte=now)
        return queryset.filter(expired_at__isnull=True) | queryset.filter(
            expired_at__gt=now
        )

    def filter_shared_with_me(self, queryset, name, value):
        if not value:
            return queryset
        from apps.sharing.models import Permission

        resource_ids = Permission.objects.filter(
            aco="Resource",
            aro="User",
            aro_foreign_key=self.request.user.pk,
        ).values_list("aco_foreign_key", flat=True)
        return queryset.filter(id__in=resource_ids).exclude(
            created_by=self.request.user
        )

    def filter_owned_by_me(self, queryset, name, value):
        if value:
            return queryset.filter(created_by=self.request.user)
        return queryset
