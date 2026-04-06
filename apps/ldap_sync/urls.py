from rest_framework.routers import DefaultRouter

from .views import LDAPConfigurationViewSet

app_name = "ldap_sync"

router = DefaultRouter()
router.register("ldap-configs", LDAPConfigurationViewSet, basename="ldap-config")

urlpatterns = router.urls
