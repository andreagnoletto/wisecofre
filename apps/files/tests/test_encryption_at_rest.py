from django.core.files.storage import default_storage

from apps.accounts.models import User
from apps.core.services import FileService
from apps.resources.models import ResourceType


def _user(db):
    return User.objects.create_user(username="fu", email="fu@x.io", password="x")


def test_text_file_content_is_encrypted_at_rest(db):
    ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    user = User.objects.create_user(username="fu", email="fu@x.io", password="x")

    fr = FileService.create_text(user, "nota", "conteudo-super-secreto")

    # bytes no storage estão cifrados (não contêm o texto claro)
    stored = default_storage.open(fr.storage_key).read()
    assert b"conteudo-super-secreto" not in stored
    assert fr.encryption_version == "fernet-v1"

    # download devolve o conteúdo original decifrado
    content, name = FileService.download(user, fr.pk)
    assert content == b"conteudo-super-secreto"


def test_upload_storage_key_has_no_path_traversal_or_name_leak(db):
    from django.core.files.uploadedfile import SimpleUploadedFile

    ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    user = User.objects.create_user(username="pt", email="pt@x.io", password="x")
    evil = SimpleUploadedFile(
        "../../../etc/senha-secreta.txt", b"conteudo", content_type="text/plain"
    )

    fr = FileService.upload(user, evil)

    assert ".." not in fr.storage_key
    assert "etc" not in fr.storage_key
    assert "senha-secreta" not in fr.storage_key  # nome cru não vaza no caminho
    assert fr.storage_key.endswith(".txt")
    # e continua recuperável
    content, _ = FileService.download(user, fr.pk)
    assert content == b"conteudo"


def test_download_of_legacy_plaintext_file_still_works(db):
    """Arquivos antigos (sem marcador fernet) continuam sendo lidos como estão."""
    from django.core.files.base import ContentFile

    from apps.files.models import FileResource, FileSecret
    from apps.resources.models import Resource

    user = User.objects.create_user(username="fu2", email="fu2@x.io", password="x")
    rt, _ = ResourceType.objects.get_or_create(slug="file", defaults={"name": "Arquivo"})
    resource = Resource.objects.create(name="legacy.txt", resource_type=rt, created_by=user)
    key = default_storage.save("files/legacy.txt", ContentFile(b"texto-antigo-claro"))
    fr = FileResource.objects.create(
        resource=resource, storage_key=key, size_bytes=18, original_name_encrypted="legacy.txt",
        mime_category="document", checksum_sha256="x", upload_completed=True, created_by=user,
        encryption_version="openpgp-aes256gcm-v1",  # marcador legado (default)
    )
    FileSecret.objects.create(file_resource=fr, user=user, session_key_encrypted="local-storage")

    content, _ = FileService.download(user, fr.pk)
    assert content == b"texto-antigo-claro"
