from rest_framework.routers import DefaultRouter

from .views import ShareViewSet

app_name = "share"

router = DefaultRouter()
router.register("", ShareViewSet, basename="share")

urlpatterns = router.urls
