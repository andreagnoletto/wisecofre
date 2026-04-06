from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Group(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_groups",
    )

    def __str__(self):
        return self.name


class GroupUser(BaseModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    is_admin = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        unique_together = [("group", "user")]

    def __str__(self):
        return f"{self.user} @ {self.group}"
