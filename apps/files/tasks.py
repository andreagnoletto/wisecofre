from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def cleanup_incomplete_uploads():
    from .models import FileResource

    cutoff = timezone.now() - timedelta(hours=1)
    stale = FileResource.objects.filter(upload_completed=False, created_at__lt=cutoff)
    count = stale.count()
    for fr in stale.iterator():
        fr.resource.delete()
    return f"{count} uploads incompletos removidos."


@shared_task
def notify_large_file_upload(file_resource_id):
    """Stub: notificar admins sobre upload de arquivo grande."""
    pass
