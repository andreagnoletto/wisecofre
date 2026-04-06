from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Folder(BaseModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    personal = models.BooleanField(default=False)

    def __str__(self):
        return self.name
