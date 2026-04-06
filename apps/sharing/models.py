import uuid

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Permission(BaseModel):
    READ = 1
    UPDATE = 7
    OWNER = 15

    TYPE_CHOICES = [
        (READ, "Read"),
        (UPDATE, "Update"),
        (OWNER, "Owner"),
    ]

    aco = models.CharField(max_length=64)
    aco_foreign_key = models.UUIDField()
    aro = models.CharField(max_length=64)
    aro_foreign_key = models.UUIDField()
    type = models.IntegerField(choices=TYPE_CHOICES, default=READ)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="granted_permissions",
    )

    class Meta(BaseModel.Meta):
        unique_together = [("aco", "aco_foreign_key", "aro", "aro_foreign_key")]
        indexes = [
            models.Index(fields=["aco", "aco_foreign_key"]),
            models.Index(fields=["aro", "aro_foreign_key"]),
        ]

    def __str__(self):
        return f"{self.aro}:{self.aro_foreign_key} -> {self.aco}:{self.aco_foreign_key} [{self.type}]"
