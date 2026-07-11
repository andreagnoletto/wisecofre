"""Backfill de Permission(aro=User) para arquivos já compartilhados.

Antes da introdução do compartilhamento com grupos, o compartilhamento direto de
arquivos criava apenas a linha FileSecret, sem uma Permission correspondente.
O SharingService trata as Permissions como fonte da verdade de "quem deve ter
acesso" e remove secrets sem permissão. Sem este backfill, o primeiro reconcile
de um arquivo revogaria os compartilhamentos diretos legados. Aqui criamos a
Permission(FileResource, User) que faltava para cada FileSecret existente.
"""
from django.db import migrations


def backfill_file_permissions(apps, schema_editor):
    FileSecret = apps.get_model("files", "FileSecret")
    Permission = apps.get_model("sharing", "Permission")
    READ = 1
    for fs in FileSecret.objects.select_related("file_resource").all():
        fr = fs.file_resource
        if fs.user_id == fr.created_by_id:
            continue
        Permission.objects.get_or_create(
            aco="FileResource",
            aco_foreign_key=fr.id,
            aro="User",
            aro_foreign_key=fs.user_id,
            defaults={"type": READ},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sharing", "0001_initial"),
        ("files", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_file_permissions, noop),
    ]
