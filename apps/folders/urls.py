from rest_framework.routers import DefaultRouter

from .views import FolderViewSet

app_name = "folders"

router = DefaultRouter()
router.register("folders", FolderViewSet, basename="folder")

urlpatterns = router.urls
