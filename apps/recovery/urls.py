from rest_framework.routers import DefaultRouter

from .views import OrganizationKeyViewSet, RecoveryRequestViewSet

app_name = "recovery"

router = DefaultRouter()
router.register("recovery-requests", RecoveryRequestViewSet, basename="recovery-request")
router.register("organization-keys", OrganizationKeyViewSet, basename="organization-key")

urlpatterns = router.urls
