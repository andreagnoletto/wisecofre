from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ResourceType(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name


class Tag(BaseModel):
    slug = models.SlugField(max_length=255)
    label = models.CharField(max_length=128)
    color = models.CharField(max_length=7, default="#000000")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )

    class Meta(BaseModel.Meta):
        unique_together = [("slug", "created_by")]

    def __str__(self):
        return self.label


class Resource(BaseModel):
    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=1024, blank=True, null=True)
    uris = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, null=True)
    resource_type = models.ForeignKey(
        ResourceType,
        on_delete=models.PROTECT,
        related_name="resources",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_resources",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_resources",
    )
    folder = models.ForeignKey(
        "folders.Folder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    expired_at = models.DateTimeField(null=True, blank=True)
    icon = models.CharField(max_length=64, blank=True, default="")
    tags = models.ManyToManyField(Tag, through="ResourceTag", blank=True)

    def __str__(self):
        return self.name


class ResourceTag(BaseModel):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta(BaseModel.Meta):
        unique_together = [("resource", "tag")]

    def __str__(self):
        return f"{self.resource} - {self.tag}"


class Secret(BaseModel):
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="secrets"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="secrets"
    )
    data = models.TextField()

    class Meta(BaseModel.Meta):
        unique_together = [("resource", "user")]

    def __str__(self):
        return f"Secret({self.resource}, {self.user})"


class SecretHistory(BaseModel):
    secret = models.ForeignKey(
        Secret, on_delete=models.CASCADE, related_name="history"
    )
    data = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="secret_history_entries",
    )

    def __str__(self):
        return f"History({self.secret}, {self.created_at})"


class Favorite(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="favorites"
    )

    class Meta(BaseModel.Meta):
        unique_together = [("user", "resource")]

    def __str__(self):
        return f"{self.user} ★ {self.resource}"
