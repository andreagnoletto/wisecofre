import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class SoftDeleteUserManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        USER = "USER", "Usuário"
        GUEST = "GUEST", "Convidado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    is_suspended = models.BooleanField(default=False)
    avatar_url = models.URLField(blank=True)
    locale = models.CharField(max_length=10, default="pt-BR")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = SoftDeleteUserManager()
    all_objects = UserManager()

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def totp_enabled(self):
        return hasattr(self, "totp_device") and self.totp_device.confirmed

    @property
    def backup_codes_count(self):
        return self.backup_codes.filter(used=False).count()

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    class Meta(AbstractUser.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class GpgKey(BaseModel):
    class KeyType(models.TextChoices):
        RSA = "RSA", "RSA"
        ECDSA = "ECDSA", "ECDSA"
        ECDH = "ECDH", "ECDH"
        EDDSA = "EdDSA", "EdDSA"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gpg_keys")
    armored_key = models.TextField()
    fingerprint = models.CharField(max_length=50, unique=True)
    bits = models.IntegerField()
    key_type = models.CharField(max_length=10, choices=KeyType.choices)
    uid = models.CharField(max_length=512)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.fingerprint} ({self.user.email})"
