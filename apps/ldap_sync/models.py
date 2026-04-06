from django.db import models

from apps.core.models import BaseModel


class LDAPConfiguration(BaseModel):
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=389)
    use_tls = models.BooleanField(default=False)
    bind_dn = models.CharField(max_length=512)
    bind_password = models.CharField(max_length=512)
    base_dn = models.CharField(max_length=512)
    user_filter = models.CharField(max_length=512, default="(objectClass=person)")
    group_filter = models.CharField(max_length=512, default="(objectClass=group)")
    sync_interval_minutes = models.IntegerField(default=60)
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"LDAP {self.host}:{self.port}"
