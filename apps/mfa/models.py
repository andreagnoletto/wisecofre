from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class TOTPDevice(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="totp_device",
    )
    secret_key = models.CharField(max_length=64)
    confirmed = models.BooleanField(default=False)

    def __str__(self):
        status = "confirmed" if self.confirmed else "unconfirmed"
        return f"TOTP({self.user}) [{status}]"


class BackupCode(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backup_codes",
    )
    code = models.CharField(max_length=20)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        status = "used" if self.used else "unused"
        return f"BackupCode({self.user}) [{status}]"
