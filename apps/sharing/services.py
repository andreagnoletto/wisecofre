"""
SharingService — autoridade central de compartilhamento.

Modelo de acesso (camada web): o acesso a uma senha/arquivo é concedido pela
existência de uma linha ``Secret``/``FileSecret`` para o usuário. As linhas
``Permission`` (ACL aco/aro) são a *fonte da verdade* de quem DEVERIA ter acesso
— incluindo grupos. Este serviço reconcilia os secrets a partir das permissões,
expandindo grupos em seus membros.

``reconcile_*`` é idempotente: cria os secrets que faltam para quem tem direito e
remove os que sobraram (nunca o do proprietário). Assim, entrar/sair de um grupo,
compartilhar ou revogar convergem sempre para o mesmo estado.
"""
from apps.groups.models import GroupUser

from .models import Permission

RESOURCE_ACO = "Resource"
FILE_ACO = "FileResource"
FOLDER_ACO = "Folder"


class SharingService:

    # ── consulta de direitos ────────────────────────────────────────────────

    @staticmethod
    def group_ids_for_user(user):
        return set(
            GroupUser.objects.filter(user=user).values_list("group_id", flat=True)
        )

    @staticmethod
    def entitled_user_ids(aco, aco_foreign_key, owner_id):
        """Conjunto de user ids que devem ter acesso: dono ∪ shares diretos ∪
        membros de grupos com permissão."""
        ids = {owner_id}
        perms = Permission.objects.filter(aco=aco, aco_foreign_key=aco_foreign_key)
        ids |= set(perms.filter(aro="User").values_list("aro_foreign_key", flat=True))
        group_ids = list(perms.filter(aro="Group").values_list("aro_foreign_key", flat=True))
        if group_ids:
            ids |= set(
                GroupUser.objects.filter(group_id__in=group_ids).values_list("user_id", flat=True)
            )
        return ids

    # ── reconciliação de secrets ────────────────────────────────────────────

    @staticmethod
    def reconcile_password_secrets(resource):
        from apps.resources.models import Secret

        owner_secret = Secret.objects.filter(
            resource=resource, user=resource.created_by
        ).first()
        data = owner_secret.data if owner_secret else ""
        entitled = SharingService.entitled_user_ids(
            RESOURCE_ACO, resource.pk, resource.created_by_id
        )
        existing = set(
            Secret.objects.filter(resource=resource).values_list("user_id", flat=True)
        )
        for uid in entitled - existing:
            Secret.objects.get_or_create(
                resource=resource, user_id=uid, defaults={"data": data}
            )
        stale = existing - entitled
        if stale:
            Secret.objects.filter(resource=resource, user_id__in=stale).delete()

    @staticmethod
    def reconcile_file_secrets(file_resource):
        from apps.files.models import FileSecret

        entitled = SharingService.entitled_user_ids(
            FILE_ACO, file_resource.pk, file_resource.created_by_id
        )
        existing = set(
            FileSecret.objects.filter(file_resource=file_resource).values_list(
                "user_id", flat=True
            )
        )
        for uid in entitled - existing:
            FileSecret.objects.get_or_create(
                file_resource=file_resource, user_id=uid,
                defaults={"session_key_encrypted": "shared"},
            )
        stale = existing - entitled
        if stale:
            FileSecret.objects.filter(
                file_resource=file_resource, user_id__in=stale
            ).delete()

    # ── compartilhamento com grupo ──────────────────────────────────────────

    @staticmethod
    def share_password_with_group(resource, group, permission_type, by_user):
        Permission.objects.update_or_create(
            aco=RESOURCE_ACO, aco_foreign_key=resource.pk,
            aro="Group", aro_foreign_key=group.pk,
            defaults={"type": permission_type, "created_by": by_user},
        )
        SharingService.reconcile_password_secrets(resource)

    @staticmethod
    def share_file_with_group(file_resource, group, permission_type, by_user):
        Permission.objects.update_or_create(
            aco=FILE_ACO, aco_foreign_key=file_resource.pk,
            aro="Group", aro_foreign_key=group.pk,
            defaults={"type": permission_type, "created_by": by_user},
        )
        SharingService.reconcile_file_secrets(file_resource)

    @staticmethod
    def unshare_group(aco, aco_foreign_key, group_pk):
        Permission.objects.filter(
            aco=aco, aco_foreign_key=aco_foreign_key,
            aro="Group", aro_foreign_key=group_pk,
        ).delete()
        SharingService._reconcile_aco(aco, aco_foreign_key)

    # ── reconciliação por mudança de grupo ──────────────────────────────────

    @staticmethod
    def on_group_membership_changed(group):
        """Ao entrar/sair um membro, reconcilia tudo que o grupo pode acessar."""
        perms = Permission.objects.filter(
            aro="Group", aro_foreign_key=group.pk
        ).values_list("aco", "aco_foreign_key")
        for aco, aco_fk in perms:
            SharingService._reconcile_aco(aco, aco_fk)

    @staticmethod
    def _reconcile_aco(aco, aco_foreign_key):
        if aco == RESOURCE_ACO:
            from apps.resources.models import Resource

            resource = Resource.objects.filter(pk=aco_foreign_key).first()
            if resource:
                SharingService.reconcile_password_secrets(resource)
        elif aco == FILE_ACO:
            from apps.files.models import FileResource

            fr = FileResource.objects.filter(pk=aco_foreign_key).first()
            if fr:
                SharingService.reconcile_file_secrets(fr)
        elif aco == FOLDER_ACO:
            SharingService.reconcile_folder(aco_foreign_key)

    # ── pastas ──────────────────────────────────────────────────────────────

    @staticmethod
    def share_folder_with_group(folder, group, permission_type, by_user):
        Permission.objects.update_or_create(
            aco=FOLDER_ACO, aco_foreign_key=folder.pk,
            aro="Group", aro_foreign_key=group.pk,
            defaults={"type": permission_type, "created_by": by_user},
        )
        SharingService.reconcile_folder(folder.pk)

    @staticmethod
    def reconcile_folder(folder_pk):
        """Compartilhar uma pasta com um grupo concede aos membros acesso a todos
        os recursos (senhas e arquivos) atualmente dentro dela. Fazemos isso
        propagando as permissões de grupo da pasta para cada recurso contido e
        reconciliando seus secrets."""
        from apps.files.models import FileResource
        from apps.resources.models import Resource

        folder_group_perms = Permission.objects.filter(
            aco=FOLDER_ACO, aco_foreign_key=folder_pk, aro="Group"
        )
        resources = Resource.objects.filter(folder_id=folder_pk, deleted_at__isnull=True)
        for resource in resources:
            for fp in folder_group_perms:
                Permission.objects.update_or_create(
                    aco=RESOURCE_ACO, aco_foreign_key=resource.pk,
                    aro="Group", aro_foreign_key=fp.aro_foreign_key,
                    defaults={"type": fp.type, "created_by_id": fp.created_by_id},
                )
            fr = FileResource.objects.filter(resource=resource).first()
            if fr:
                for fp in folder_group_perms:
                    Permission.objects.update_or_create(
                        aco=FILE_ACO, aco_foreign_key=fr.pk,
                        aro="Group", aro_foreign_key=fp.aro_foreign_key,
                        defaults={"type": fp.type, "created_by_id": fp.created_by_id},
                    )
                SharingService.reconcile_file_secrets(fr)
            else:
                SharingService.reconcile_password_secrets(resource)
