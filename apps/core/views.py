from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        checks = {}
        healthy = True

        try:
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = str(e)
            healthy = False

        try:
            import boto3
            from django.conf import settings

            s3 = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            )
            s3.head_bucket(Bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", "wisecofre"))
            checks["minio"] = "ok"
        except Exception as e:
            checks["minio"] = str(e)
            healthy = False

        status_code = 200 if healthy else 503
        return Response({"status": "healthy" if healthy else "unhealthy", "checks": checks}, status=status_code)
