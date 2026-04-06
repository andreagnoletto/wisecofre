from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.core.models import SystemConfiguration
from apps.resources.models import ResourceType


DEFAULT_RESOURCE_TYPES = [
    {"name": "Password", "slug": "password", "description": "Credencial de senha"},
    {"name": "TOTP", "slug": "totp", "description": "Segredo TOTP (2FA)"},
    {"name": "Note", "slug": "note", "description": "Nota segura"},
    {"name": "Key-Value", "slug": "key_value", "description": "Par chave-valor genérico"},
    {"name": "SSH Key", "slug": "ssh_key", "description": "Chave SSH"},
    {"name": "Credit Card", "slug": "credit_card", "description": "Cartão de crédito"},
    {"name": "File", "slug": "file", "description": "Arquivo criptografado"},
]

DEFAULT_CONFIGURATIONS = [
    {
        "key": "FILE_MAX_SIZE_BYTES",
        "value": 10 * 1024 * 1024,
        "description": "Tamanho máximo de upload de arquivo em bytes",
    },
    {
        "key": "SESSION_TIMEOUT_MINUTES",
        "value": 30,
        "description": "Tempo de expiração da sessão em minutos",
    },
    {
        "key": "MAX_LOGIN_ATTEMPTS",
        "value": 5,
        "description": "Número máximo de tentativas de login antes do bloqueio",
    },
    {
        "key": "PASSWORD_EXPIRY_DAYS",
        "value": 90,
        "description": "Dias até a expiração de senha",
    },
]


class Command(BaseCommand):
    help = "Configura dados iniciais do Wisecofre (tipos de recurso, configurações do sistema, admin opcional)"

    def add_arguments(self, parser):
        parser.add_argument("--create-admin", action="store_true", help="Cria usuário admin padrão")
        parser.add_argument("--admin-email", default="admin@wisecofre.io")
        parser.add_argument("--admin-password", default="admin123!@#")

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Wisecofre Setup"))
        self.stdout.write("")

        rt_created = 0
        for rt in DEFAULT_RESOURCE_TYPES:
            _, created = ResourceType.objects.get_or_create(slug=rt["slug"], defaults=rt)
            if created:
                rt_created += 1
        self.stdout.write(f"  ResourceTypes: {rt_created} criados, {len(DEFAULT_RESOURCE_TYPES) - rt_created} já existiam")

        cfg_created = 0
        for cfg in DEFAULT_CONFIGURATIONS:
            _, created = SystemConfiguration.objects.get_or_create(key=cfg["key"], defaults=cfg)
            if created:
                cfg_created += 1
        self.stdout.write(f"  SystemConfigurations: {cfg_created} criadas, {len(DEFAULT_CONFIGURATIONS) - cfg_created} já existiam")

        if options["create_admin"]:
            email = options["admin_email"]
            password = options["admin_password"]
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"  Admin: {email} já existe")
            else:
                User.objects.create_superuser(
                    username="admin",
                    email=email,
                    password=password,
                    role=User.Role.ADMIN,
                    first_name="Admin",
                    last_name="Wisecofre",
                )
                self.stdout.write(f"  Admin: {email} criado com sucesso")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Setup concluído!"))
