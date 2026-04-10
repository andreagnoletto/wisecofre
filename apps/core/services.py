"""
Service layer — centraliza autorização e lógica de negócio.
Views chamam services; services levantam PermissionDenied/ValidationError.
"""
import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.files.models import FileResource, FileSecret
from apps.folders.models import Folder
from apps.groups.models import Group, GroupUser
from apps.resources.models import Resource, ResourceType, Secret, Tag
from apps.sharing.models import Permission


# ── Passwords ─────────────────────────────────────────────────────────────

class PasswordService:

    @staticmethod
    def get_or_deny(user, pk):
        resource = get_object_or_404(Resource, pk=pk, deleted_at__isnull=True)
        secret = Secret.objects.filter(resource=resource, user=user).first()
        if not secret and not user.is_staff:
            raise PermissionDenied("Sem acesso a esta senha.")
        return resource, secret

    @staticmethod
    def create(user, *, name, secret_data, username=None, uri=None,
               description=None, folder_id=None, tags_raw=""):
        if not name:
            raise ValidationError("Nome é obrigatório.")
        rt, _ = ResourceType.objects.get_or_create(slug="password", defaults={"name": "Senha"})
        resource = Resource.objects.create(
            name=name, username=username, uri=uri, description=description,
            resource_type=rt, created_by=user, folder_id=folder_id,
        )
        Secret.objects.create(resource=resource, user=user, data=secret_data)
        if tags_raw:
            from django.utils.text import slugify
            for label in tags_raw.split(","):
                label = label.strip()
                if label:
                    tag, _ = Tag.objects.get_or_create(
                        slug=slugify(label), created_by=user,
                        defaults={"label": label},
                    )
                    resource.tags.add(tag)
        return resource

    @staticmethod
    def update(user, pk, *, name, username=None, uri=None,
               description=None, folder_id=None, secret_data=None):
        resource, secret = PasswordService.get_or_deny(user, pk)
        if resource.created_by != user:
            perm = Permission.objects.filter(
                aco="Resource", aco_foreign_key=resource.pk,
                aro="User", aro_foreign_key=user.pk, type__gte=Permission.UPDATE,
            ).first()
            if not perm and not user.is_staff:
                raise PermissionDenied("Sem permissão para editar.")
        if not name:
            raise ValidationError("Nome é obrigatório.")
        resource.name = name
        resource.username = username
        resource.uri = uri
        resource.description = description
        resource.folder_id = folder_id
        resource.modified_by = user
        resource.save()
        if secret_data:
            if secret:
                secret.data = secret_data
                secret.save()
            else:
                Secret.objects.create(resource=resource, user=user, data=secret_data)
        return resource, secret

    @staticmethod
    def delete(user, pk):
        resource = get_object_or_404(Resource, pk=pk)
        if resource.created_by != user and not user.is_staff:
            raise PermissionDenied("Apenas o proprietário pode excluir.")
        Secret.objects.filter(resource=resource).delete()
        Permission.objects.filter(aco="Resource", aco_foreign_key=resource.pk).delete()
        resource.hard_delete()

    @staticmethod
    def share(user, pk, target_email, permission_type="read"):
        resource = get_object_or_404(Resource, pk=pk)
        owner_secret = Secret.objects.filter(resource=resource, user=user).first()
        if not owner_secret:
            raise PermissionDenied("Sem permissão para compartilhar.")
        try:
            target = User.objects.get(email=target_email)
        except User.DoesNotExist:
            raise ValidationError("Usuário não encontrado.")
        if target == user:
            raise ValidationError("Você já tem acesso a esta senha.")
        Secret.objects.update_or_create(
            resource=resource, user=target,
            defaults={"data": owner_secret.data},
        )
        perm_map = {"read": Permission.READ, "write": Permission.UPDATE}
        Permission.objects.update_or_create(
            aco="Resource", aco_foreign_key=resource.pk,
            aro="User", aro_foreign_key=target.pk,
            defaults={"type": perm_map.get(permission_type, Permission.READ), "created_by": user},
        )
        return target


# ── Folders ───────────────────────────────────────────────────────────────

class FolderService:

    @staticmethod
    def create(user, *, name, parent_id=None):
        if not name:
            raise ValidationError("Nome da pasta é obrigatório.")
        return Folder.objects.create(name=name, parent_id=parent_id, created_by=user)

    @staticmethod
    def delete(user, pk):
        folder = get_object_or_404(Folder, pk=pk)
        if folder.created_by != user and not user.is_staff:
            raise PermissionDenied("Apenas o proprietário pode excluir esta pasta.")
        folder.hard_delete()


# ── Groups ────────────────────────────────────────────────────────────────

class GroupService:

    @staticmethod
    def _require_member(user, group):
        if not GroupUser.objects.filter(group=group, user=user).exists():
            if not user.is_staff:
                raise PermissionDenied("Você não é membro deste grupo.")

    @staticmethod
    def _require_admin(user, group):
        if not GroupUser.objects.filter(group=group, user=user, is_admin=True).exists():
            if not user.is_staff:
                raise PermissionDenied("Apenas administradores do grupo podem realizar esta ação.")

    @staticmethod
    def list_for_user(user):
        if user.is_staff:
            return Group.objects.filter(deleted_at__isnull=True).prefetch_related("members__user")
        member_group_ids = GroupUser.objects.filter(user=user).values_list("group_id", flat=True)
        return Group.objects.filter(
            pk__in=member_group_ids, deleted_at__isnull=True,
        ).prefetch_related("members__user")

    @staticmethod
    def get_detail(user, pk):
        group = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        GroupService._require_member(user, group)
        members = GroupUser.objects.filter(group=group).select_related("user")
        is_admin = GroupUser.objects.filter(group=group, user=user, is_admin=True).exists() or user.is_staff
        member_user_ids = members.values_list("user_id", flat=True)
        available_users = User.objects.filter(
            deleted_at__isnull=True, is_active=True,
        ).exclude(id__in=member_user_ids) if is_admin else User.objects.none()
        return group, members, available_users, is_admin

    @staticmethod
    def edit(user, pk, name):
        group = get_object_or_404(Group, pk=pk)
        GroupService._require_admin(user, group)
        group.name = name
        group.save()
        return group

    @staticmethod
    def delete(user, pk):
        group = get_object_or_404(Group, pk=pk)
        GroupService._require_admin(user, group)
        GroupUser.objects.filter(group=group).delete()
        group.hard_delete()

    @staticmethod
    def add_member(user, group_pk, *, user_id=None, email=None):
        group = get_object_or_404(Group, pk=group_pk)
        GroupService._require_admin(user, group)
        if user_id:
            try:
                target = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                raise ValidationError("Usuário não encontrado.")
        elif email:
            try:
                target = User.objects.get(email=email)
            except User.DoesNotExist:
                raise ValidationError("Usuário não encontrado.")
        else:
            raise ValidationError("Informe o usuário.")
        GroupUser.objects.get_or_create(group=group, user=target)
        return target

    @staticmethod
    def remove_member(user, group_pk, target_user_pk):
        group = get_object_or_404(Group, pk=group_pk)
        GroupService._require_admin(user, group)
        GroupUser.objects.filter(group=group, user_id=target_user_pk).delete()

    @staticmethod
    def toggle_admin(user, group_pk, target_user_pk):
        group = get_object_or_404(Group, pk=group_pk)
        GroupService._require_admin(user, group)
        gu = get_object_or_404(GroupUser, group=group, user_id=target_user_pk)
        gu.is_admin = not gu.is_admin
        gu.save()


# ── Files ─────────────────────────────────────────────────────────────────

class FileService:

    @staticmethod
    def get_or_deny(user, pk):
        fr = get_object_or_404(FileResource, pk=pk, deleted_at__isnull=True)
        secret = FileSecret.objects.filter(file_resource=fr, user=user).first()
        if not secret and not user.is_staff:
            raise PermissionDenied("Sem acesso a este arquivo.")
        return fr, secret

    @staticmethod
    def _classify_mime(mime):
        mime = mime or ""
        if "image" in mime:
            return "image"
        if "pdf" in mime or "word" in mime or "text" in mime:
            return "document"
        if "zip" in mime or "rar" in mime or "tar" in mime or "gzip" in mime:
            return "archive"
        if "sheet" in mime or "excel" in mime or "csv" in mime:
            return "spreadsheet"
        if "key" in mime or "pgp" in mime or "cert" in mime or "pem" in mime:
            return "key"
        return "other"

    @staticmethod
    def upload(user, uploaded_file, folder_id=None):
        if uploaded_file.size > 10 * 1024 * 1024:
            raise ValidationError("Arquivo excede o tamanho máximo de 10 MB.")
        hasher = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            hasher.update(chunk)
        checksum = hasher.hexdigest()
        uploaded_file.seek(0)

        storage_key = f"files/{user.pk}/{checksum[:8]}_{uploaded_file.name}"
        saved_path = default_storage.save(storage_key, uploaded_file)
        cat = FileService._classify_mime(uploaded_file.content_type)

        rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
        resource = Resource.objects.create(
            name=uploaded_file.name, resource_type=rt,
            created_by=user, folder_id=folder_id,
        )
        fr = FileResource.objects.create(
            resource=resource, storage_key=saved_path, size_bytes=uploaded_file.size,
            original_name_encrypted=uploaded_file.name, mime_category=cat,
            checksum_sha256=checksum, upload_completed=True, created_by=user,
        )
        FileSecret.objects.create(
            file_resource=fr, user=user, session_key_encrypted="local-storage",
        )
        return fr

    @staticmethod
    def create_text(user, name, content, folder_id=None):
        raw = content.encode("utf-8")
        if len(raw) > 10 * 1024 * 1024:
            raise ValidationError("Conteúdo excede o tamanho máximo de 10 MB.")
        checksum = hashlib.sha256(raw).hexdigest()
        if not name.endswith(".txt"):
            name += ".txt"
        storage_key = f"files/{user.pk}/{checksum[:8]}_{name}"
        saved_path = default_storage.save(storage_key, ContentFile(raw))

        rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
        resource = Resource.objects.create(
            name=name, resource_type=rt,
            created_by=user, folder_id=folder_id,
        )
        fr = FileResource.objects.create(
            resource=resource, storage_key=saved_path, size_bytes=len(raw),
            original_name_encrypted=name, mime_category="document",
            checksum_sha256=checksum, upload_completed=True, created_by=user,
        )
        FileSecret.objects.create(
            file_resource=fr, user=user, session_key_encrypted="local-storage",
        )
        return fr

    @staticmethod
    def download(user, pk):
        fr, _ = FileService.get_or_deny(user, pk)
        if not default_storage.exists(fr.storage_key):
            raise ValidationError("Arquivo não encontrado no storage.")
        f = default_storage.open(fr.storage_key, "rb")
        content = f.read()
        f.close()
        safe_name = fr.original_name_encrypted.replace('"', "'").replace("\n", "").replace("\r", "")
        return content, safe_name

    @staticmethod
    def delete(user, pk):
        fr = get_object_or_404(FileResource, pk=pk)
        if fr.created_by != user and not user.is_staff:
            raise PermissionDenied("Apenas o proprietário pode excluir este arquivo.")
        try:
            if fr.storage_key and default_storage.exists(fr.storage_key):
                default_storage.delete(fr.storage_key)
        except Exception:
            pass
        FileSecret.objects.filter(file_resource=fr).delete()
        resource = fr.resource
        fr.hard_delete()
        resource.hard_delete()

    @staticmethod
    def share(user, pk, target_query):
        fr = get_object_or_404(FileResource, pk=pk)
        if not FileSecret.objects.filter(file_resource=fr, user=user).exists():
            if not user.is_staff:
                raise PermissionDenied("Sem permissão para compartilhar.")
        if not target_query:
            raise ValidationError("Informe o nome ou e-mail do usuário.")
        target = User.objects.filter(email__iexact=target_query).first()
        if not target:
            target = User.objects.filter(first_name__icontains=target_query).first()
        if not target:
            raise ValidationError("Usuário não encontrado.")
        if target == user:
            raise ValidationError("Você já tem acesso a este arquivo.")
        FileSecret.objects.update_or_create(
            file_resource=fr, user=target,
            defaults={"session_key_encrypted": "shared"},
        )
        return target

    @staticmethod
    def unshare(user, pk, target_user_id):
        fr = get_object_or_404(FileResource, pk=pk)
        if fr.created_by != user and not user.is_staff:
            raise PermissionDenied("Apenas o proprietário pode revogar acesso.")
        FileSecret.objects.filter(file_resource=fr, user_id=target_user_id).delete()
