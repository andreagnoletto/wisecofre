from django.db import models

from apps.core.models import BaseModel


class SSOProvider(BaseModel):
    class Provider(models.TextChoices):
        MICROSOFT = "microsoft", "Microsoft"
        GOOGLE = "google", "Google"
        OIDC = "oidc", "OpenID Connect"
        ADFS = "adfs", "ADFS"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    client_id = models.CharField(max_length=512)
    client_secret = models.CharField(max_length=512)
    tenant_id = models.CharField(max_length=255, blank=True, default="")
    discovery_url = models.URLField(blank=True, default="")
    is_enabled = models.BooleanField(default=False)
    allow_registration = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_provider_display()} ({'enabled' if self.is_enabled else 'disabled'})"
