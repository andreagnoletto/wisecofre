from rest_framework.routers import DefaultRouter

from .views import ActionLogViewSet

app_name = "audit"

router = DefaultRouter()
router.register("action-logs", ActionLogViewSet, basename="action-log")

urlpatterns = router.urls
