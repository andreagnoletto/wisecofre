import uuid

from django.utils import timezone
from rest_framework.renderers import JSONRenderer


class WisecofreRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        status_code = response.status_code if response else 200

        is_success = 200 <= status_code < 400
        body_data = data
        pagination = None

        if isinstance(data, dict) and "results" in data:
            pagination = {
                "count": data.get("count"),
                "next": data.get("next"),
                "previous": data.get("previous"),
            }
            body_data = data["results"]

        envelope = {
            "header": {
                "id": str(uuid.uuid4()),
                "status": "success" if is_success else "error",
                "servertime": int(timezone.now().timestamp()),
                "code": status_code,
                "message": self._get_message(data, is_success),
            },
            "body": {
                "data": body_data,
                "pagination": pagination,
            },
        }

        return super().render(envelope, accepted_media_type, renderer_context)

    @staticmethod
    def _get_message(data, is_success):
        if is_success:
            return "OK"
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
        return "An error occurred."
