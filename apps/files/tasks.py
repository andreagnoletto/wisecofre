from django.utils import timezone
from datetime import timedelta


def cleanup_incomplete_uploads():
    from .models import FileResource

    cutoff = timezone.now() - timedelta(hours=1)
    stale = FileResource.objects.filter(upload_completed=False, created_at__lt=cutoff)
    count = stale.count()
    for fr in stale.iterator():
        fr.resource.delete()
    return f"{count} uploads incompletos removidos."
