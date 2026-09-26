import secrets
from datetime import timedelta
import resend

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.parsers import FormParser, MultiPartParser

from .models import EmailOTP, User
from .permissions import IsVerifiedUser
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    OTPVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetSerializer,
    ProfileSerializer,
    MessageSerializer,
    RegistrationResponseSerializer,
    ResetTokenResponseSerializer,
    RegistrationSerializer,
    ResendOTPSerializer,
    TokenResponseSerializer,
    UserSummarySerializer,
    load_reset_token,
)


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



# production
def send_otp_email(otp):
    recipient = (
        otp.user.pending_email
        if otp.purpose == EmailOTP.EMAIL_CHANGE
        else otp.user.email
    )

    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send({
        "from": "TradeSim <noreply@pradipkunwar.name.np>",
        "to": [recipient],
        "subject": "Your TradeSim verification code",
        "text": (
            f"Your TradeSim code is {otp.otp}\n\n"
            f"It expires in {settings.OTP_EXPIRATION_MINUTES} minutes."
        ),
    })

# # development
# def send_otp_email(otp):
#     recipient = (
#         otp.user.pending_email
#         if otp.purpose == EmailOTP.EMAIL_CHANGE
#         else otp.user.email
#     )

#     send_mail(
#         subject= "Your TradeSim verification code",
#         message=f"Your TradeSim code is {otp.otp}\n\n It expires in {settings.OTP_EXPIRATION_MINUTES} minutes.",
#         from_email=settings.EMAIL_HOST_USER,
#         recipient_list=[recipient]
#     )

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=RegistrationSerializer,
        responses={201: RegistrationResponseSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(is_verified=False)
        otp = create_otp(user, EmailOTP.REGISTRATION_VERIFICATION)
        send_otp_email(otp)
        return Response(
            {
                "message": "Registration successful. Check your email to verify your account.",
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=OTPVerificationSerializer,
        responses=MessageSerializer,
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        otp_value = serializer.validated_data["otp"]

        try:
            otp = EmailOTP.objects.select_related("user").get(
                user__email__iexact=email,
                otp=otp_value,
                purpose=EmailOTP.REGISTRATION_VERIFICATION,
                is_used=False,
            )
        except EmailOTP.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.expires_at <= timezone.now():
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        otp.user.is_verified = True
        otp.user.is_active = True
        otp.user.save(update_fields=["is_verified", "is_active", "updated_at"])
        return Response({"message": "Email verified successfully."})


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=ResendOTPSerializer,
        responses=MessageSerializer,
    )
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_verified=False).first()
        if user:
            otp = create_otp(user, EmailOTP.REGISTRATION_VERIFICATION)
            send_otp_email(otp)
        return Response(
            {"message": "If the account can receive a code, a new OTP has been sent."}
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=LoginSerializer,
        responses=TokenResponseSerializer,
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class ChangePasswordView(APIView):
    permission_classes = [IsVerifiedUser]

    @extend_schema(
        tags=["Auth"],
        request=ChangePasswordSerializer,
        responses=MessageSerializer,
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return Response({"message": "Password changed successfully."})


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=PasswordResetRequestSerializer,
        responses=MessageSerializer,
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            otp = create_otp(user, EmailOTP.PASSWORD_RESET)
            send_otp_email(otp)
        return Response(
            {"message": "If the account exists, a password reset code has been sent."}
        )


class PasswordResetOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=OTPVerificationSerializer,
        responses=ResetTokenResponseSerializer,
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        try:
            otp = EmailOTP.objects.get(
                user__email__iexact=email,
                otp=serializer.validated_data["otp"],
                purpose=EmailOTP.PASSWORD_RESET,
                is_used=False,
            )
        except EmailOTP.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if otp.expires_at <= timezone.now():
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        reset_token = signing.dumps({"otp_id": otp.pk, "user_id": otp.user_id})
        return Response({"reset_token": reset_token})


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=PasswordResetSerializer,
        responses=MessageSerializer,
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = load_reset_token(serializer.validated_data["reset_token"])
        otp.user.set_password(serializer.validated_data["new_password"])
        otp.user.save(update_fields=["password", "updated_at"])
        otp.expires_at = timezone.now()
        otp.save(update_fields=["expires_at"])
        return Response({"message": "Password reset successfully."})

class ProfileView(APIView):
    permission_classes = [IsVerifiedUser]
    parser_classes = [FormParser, MultiPartParser]

    @extend_schema(
        tags=["Profile"],
        responses=ProfileSerializer,
    )
    def get(self, request):
        return Response(
            ProfileSerializer(
                request.user,
                context={"request": request},
            ).data
        )

    @extend_schema(
        tags=["Profile"],
        request=ProfileSerializer,
        responses=ProfileSerializer,
    )
    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        new_email = serializer.validated_data.pop("email", None)

        if new_email and new_email != request.user.email:
            request.user.pending_email = new_email
            request.user.save(
                update_fields=["pending_email", "updated_at"]
            )

            otp = create_otp(
                request.user,
                EmailOTP.EMAIL_CHANGE,
            )
            send_otp_email(otp)

            return Response(
                {
                    "message": "Verification code sent to the new email address.",
                    "profile": ProfileSerializer(
                        request.user,
                        context={"request": request},
                    ).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        user = serializer.save()

        return Response(
            ProfileSerializer(
                user,
                context={"request": request},
            ).data
        )


class VerifyEmailChangeView(APIView):
    permission_classes = [IsVerifiedUser]

    @extend_schema(
        tags=["Profile"], request=OTPVerificationSerializer, responses=MessageSerializer
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = EmailOTP.objects.filter(
            user=request.user,
            purpose=EmailOTP.EMAIL_CHANGE,
            otp=serializer.validated_data["otp"],
            is_used=False,
        ).first()
        if (
            not otp
            or otp.expires_at <= timezone.now()
            or request.user.pending_email != serializer.validated_data["email"].lower()
        ):
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.email = request.user.pending_email
        request.user.pending_email = None
        request.user.save(update_fields=["email", "pending_email", "updated_at"])
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return Response({"message": "Email changed successfully."})


@extend_schema(tags=["Auth"])
class RefreshTokenView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


# Create your views here.
