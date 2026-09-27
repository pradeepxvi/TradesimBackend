
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)


from django.core.mail import send_mail
import secrets
from datetime import timedelta

from .models import EmailOTP, User
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string


def generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def create_otp(user, purpose):
    EmailOTP.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)
    otp = EmailOTP.objects.create(
        user=user,
        otp=generate_otp(),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES),
    )
    return otp



def send_otp_email(otp: EmailOTP):
    """
    Send an OTP email for registration verification,
    password reset, or email change.
    """

    # Determine where the OTP should be sent.
    if otp.purpose == EmailOTP.EMAIL_CHANGE:
        recipient = otp.user.pending_email
    else:
        recipient = otp.user.email

    # Determine the purpose text shown in the email.
    purpose_text = {
        EmailOTP.REGISTRATION_VERIFICATION: "Verify your account",
        EmailOTP.PASSWORD_RESET: "Change your password",
        EmailOTP.EMAIL_CHANGE: "Change your email address",
    }.get(otp.purpose, "Verify your account")

    # Render HTML email.
    html_content = render_to_string(
        "email.html",
        {
            "otp": otp.otp,
            "name": otp.user.full_name,
            "purpose": purpose_text,
        },
    )

    client = Brevo(api_key=settings.BREVO_API_KEY)

    client.transactional_emails.send_transac_email(
        subject=f"TradeSim - {purpose_text}",
        html_content=html_content,
        sender=SendTransacEmailRequestSender(
            email=settings.BREVO_SENDER_EMAIL,
            name="TradeSim",
        ),
        to=[
            SendTransacEmailRequestToItem(
                email=recipient,
                name=otp.user.full_name or "TradeSim User",
            )
        ],
    )