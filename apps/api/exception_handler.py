import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def wisecofre_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        return Response(
            _build_error_envelope(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal server error.",
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    errors = response.data
    if isinstance(errors, dict) and "detail" in errors:
        message = str(errors["detail"])
    elif isinstance(errors, list):
        message = errors[0] if errors else "Validation error."
    else:
        message = "Validation error."

    response.data = _build_error_envelope(
        response.status_code,
        message,
        errors=errors,
    )
    return response


def _build_error_envelope(status_code, message, errors=None):
    return {
        "header": {
            "id": str(uuid.uuid4()),
            "status": "error",
            "servertime": int(timezone.now().timestamp()),
            "code": status_code,
            "message": message,
        },
        "body": {
            "data": errors,
            "pagination": None,
        },
    }
