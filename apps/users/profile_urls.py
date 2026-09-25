"""Authenticated profile routes."""

from django.urls import path

from .views import ProfileView, VerifyEmailChangeView

urlpatterns = [
    path("", ProfileView.as_view(), name="profile"),
    path(
        "verify-email-change/",
        VerifyEmailChangeView.as_view(),
        name="verify-email-change",
    ),
]
