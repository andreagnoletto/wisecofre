from rest_framework.routers import DefaultRouter

from .views import ResourceTypeViewSet, ResourceViewSet, TagViewSet

app_name = "resources"

router = DefaultRouter()
router.register("resources", ResourceViewSet, basename="resource")
router.register("types", ResourceTypeViewSet, basename="resource-type")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = router.urls
