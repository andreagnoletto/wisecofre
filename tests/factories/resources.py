import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.resources.models import Resource, ResourceType, Secret


class ResourceTypeFactory(DjangoModelFactory):
    class Meta:
        model = ResourceType

    name = factory.Sequence(lambda n: f"Type {n}")
    slug = factory.Sequence(lambda n: f"type-{n}")
    description = factory.Faker("sentence")


class ResourceFactory(DjangoModelFactory):
    class Meta:
        model = Resource

    name = factory.Faker("word")
    resource_type = factory.SubFactory(ResourceTypeFactory)
    created_by = factory.SubFactory("tests.factories.accounts.UserFactory")
    modified_by = factory.LazyAttribute(lambda o: o.created_by)


class SecretFactory(DjangoModelFactory):
    class Meta:
        model = Secret

    resource = factory.SubFactory(ResourceFactory)
    user = factory.SubFactory("tests.factories.accounts.UserFactory")
    data = factory.Faker("sha256")
