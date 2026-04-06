from rest_framework.routers import DefaultRouter

from .views import FileViewSet

app_name = "files"

router = DefaultRouter()
router.register("files", FileViewSet, basename="file")

urlpatterns = router.urls
