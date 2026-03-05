from django.urls import path
from .views import (
    GymOwnerRegisterView,
    VerifyEmailOtpView,
    ResendOtpView,
    GymOwnerLoginView,
    ForgotPasswordView,
    VerifyForgotPasswordOtpView,
    ResetPasswordView,
    GetProfileView,
)

urlpatterns = [
    path("register/", GymOwnerRegisterView.as_view(), name="org-register"),
    path("verify-otp/", VerifyEmailOtpView.as_view(), name="org-verify-otp"),
    path("resend-otp/", ResendOtpView.as_view(), name="org-resend-otp"),
    path("login/", GymOwnerLoginView.as_view(), name="org-login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="org-forgot-password"),
    path("verify-forgot-password-otp/", VerifyForgotPasswordOtpView.as_view(), name="org-verify-forgot-password-otp"),
    path("reset-password/", ResetPasswordView.as_view(), name="org-reset-password"),
    path("profile/", GetProfileView.as_view(), name="org-profile"),
]
