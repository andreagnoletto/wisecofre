from rest_framework.routers import DefaultRouter

from .views import PermissionViewSet

app_name = "permissions"

router = DefaultRouter()
router.register("", PermissionViewSet, basename="permission")

urlpatterns = router.urls
