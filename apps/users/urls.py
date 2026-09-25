"""Authentication URL routes."""

from django.urls import path

from .views import (
    ChangePasswordView,
    LoginView,
    PasswordResetOTPView,
    PasswordResetRequestView,
    PasswordResetView,
    RefreshTokenView,
    RegisterView,
    ResendOTPView,
    VerifyOTPView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/verify-otp/",
        PasswordResetOTPView.as_view(),
        name="password-reset-verify-otp",
    ),
    path("password-reset/", PasswordResetView.as_view(), name="password-reset"),
]
