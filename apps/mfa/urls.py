from django.urls import path

from .views import BackupCodesView, TOTPDeleteView, TOTPSetupView, TOTPVerifyView

app_name = "mfa"

urlpatterns = [
    path("totp/setup/", TOTPSetupView.as_view(), name="totp-setup"),
    path("totp/verify/", TOTPVerifyView.as_view(), name="totp-verify"),
    path("totp/delete/", TOTPDeleteView.as_view(), name="totp-delete"),
    path("backup-codes/", BackupCodesView.as_view(), name="backup-codes"),
]
