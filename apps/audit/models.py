from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ActionLog(BaseModel):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAIL = "fail", "Fail"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="action_logs",
    )
    action = models.CharField(max_length=128)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=7, choices=Status.choices)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, default="")

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} [{self.status}] - {self.user}"
