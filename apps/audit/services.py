from .models import ActionLog


def log_action(user, action, status, ip_address, user_agent="", context=None):
    return ActionLog.objects.create(
        user=user,
        action=action,
        status=status,
        ip_address=ip_address,
        user_agent=user_agent,
        context=context or {},
    )
