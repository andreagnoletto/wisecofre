from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Notification(BaseModel):
    class Type(models.TextChoices):
        SHARE = "share", "Share"
        REVOKE = "revoke", "Revoke"
        EXPIRY = "expiry", "Expiry"
        INVITE = "invite", "Invite"
        SECURITY = "security", "Security"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=64, choices=Type.choices)
    is_read = models.BooleanField(default=False)
    related_resource_id = models.UUIDField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} → {self.recipient}"
