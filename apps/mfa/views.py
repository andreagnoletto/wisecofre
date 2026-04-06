import secrets

import pyotp
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BackupCode, TOTPDevice
from .serializers import BackupCodeSerializer, TOTPSetupSerializer, TOTPVerifySerializer


class TOTPSetupView(APIView):
    """QR code is generated client-side from the provisioning_uri via Alpine.js."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
            return Response(
                {"detail": "TOTP already configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()

        secret = pyotp.random_base32()
        TOTPDevice.objects.create(user=request.user, secret_key=secret)

        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=request.user.email,
            issuer_name="Wisecofre",
        )

        return Response(
            {"provisioning_uri": provisioning_uri, "secret": secret},
            status=status.HTTP_201_CREATED,
        )


class TOTPVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            device = TOTPDevice.objects.get(user=request.user)
        except TOTPDevice.DoesNotExist:
            return Response(
                {"detail": "No TOTP device found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        totp = pyotp.TOTP(device.secret_key)
        if not totp.verify(serializer.validated_data["code"]):
            return Response(
                {"detail": "Invalid code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not device.confirmed:
            device.confirmed = True
            device.save(update_fields=["confirmed"])

        return Response({"detail": "Code verified."})


class TOTPDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        deleted, _ = TOTPDevice.objects.filter(user=request.user).delete()
        if not deleted:
            return Response(
                {"detail": "No TOTP device found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        BackupCode.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BackupCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        codes = BackupCode.objects.filter(user=request.user, used=False)
        return Response(BackupCodeSerializer(codes, many=True).data)

    def post(self, request):
        """Regenerate backup codes."""
        if not TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
            return Response(
                {"detail": "TOTP not configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        BackupCode.objects.filter(user=request.user).delete()
        codes = [
            BackupCode(user=request.user, code=secrets.token_hex(5))
            for _ in range(10)
        ]
        BackupCode.objects.bulk_create(codes)
        return Response(
            BackupCodeSerializer(codes, many=True).data,
            status=status.HTTP_201_CREATED,
        )
