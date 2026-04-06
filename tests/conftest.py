import pytest
from django.test import RequestFactory
from apps.accounts.models import User


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        email='test@wisecofre.io',
        password='testpass123',
        first_name='Test',
        last_name='User',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='admin',
        email='admin@wisecofre.io',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        role='ADMIN',
        is_staff=True,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username='other',
        email='other@wisecofre.io',
        password='otherpass123',
        first_name='Other',
        last_name='User',
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def resource_type_file(db):
    from apps.resources.models import ResourceType
    return ResourceType.objects.create(name='File', slug='file', description='Encrypted file')


@pytest.fixture
def resource_type_password(db):
    from apps.resources.models import ResourceType
    return ResourceType.objects.create(name='Password', slug='password', description='Password credential')
