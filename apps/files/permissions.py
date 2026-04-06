from rest_framework.permissions import BasePermission


class HasFileAccess(BasePermission):
    """Verifica se o usuário possui um FileSecret para o arquivo."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        return obj.secrets.filter(user=request.user).exists()
