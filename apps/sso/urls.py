from rest_framework.routers import DefaultRouter

from .views import SSOProviderViewSet

app_name = "sso"

router = DefaultRouter()
router.register("sso-providers", SSOProviderViewSet, basename="sso-provider")

urlpatterns = router.urls
