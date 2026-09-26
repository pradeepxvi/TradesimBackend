from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import EmailOTP

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "is_verified")


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "profile_picture",
            "is_verified",
            "date_joined",
        )
        read_only_fields = ("id", "is_verified", "date_joined")
        extra_kwargs = {"email": {"required": False}}

    def validate_email(self, value):
        email = value.strip().lower()
        user = self.instance
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_profile_picture(self, image):
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "Profile picture must be 5 MB or smaller."
            )
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if image.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only JPEG, PNG, and WebP images are allowed."
            )
        return image

    def get_profile_picture(self, obj): 
        if not obj.profile_picture: 
            return None 
        request = self.context.get("request") 
        if request: 
            return request.build_absolute_uri( obj.profile_picture.url ) 
        return obj.profile_picture.url


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class RegistrationResponseSerializer(MessageSerializer):
    user = UserSummarySerializer()


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer()


class ResetTokenResponseSerializer(serializers.Serializer):
    reset_token = serializers.CharField()


class RegistrationSerializer(serializers.ModelSerializer):
    password_confirmation = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "password_confirmation", "full_name")
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirmation"):
            raise serializers.ValidationError(
                {"password_confirmation": "Passwords do not match."}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only numbers.")
        return value


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(
            self.context.get("request"),
            email=email,
            password=password,
        )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        if not user.is_verified:
            raise serializers.ValidationError("Please verify your email first.")

        data = super().validate(attrs)
        data["user"] = UserSummarySerializer(user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        validate_password(attrs["new_password"], user)
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        validate_password(attrs["new_password"])
        return attrs


def load_reset_token(token):
    try:
        data = signing.loads(token, max_age=settings.OTP_EXPIRATION_MINUTES * 60)
    except signing.BadSignature as exc:
        raise serializers.ValidationError("Invalid or expired reset token.") from exc

    try:
        otp = EmailOTP.objects.select_related("user").get(
            pk=data["otp_id"],
            user_id=data["user_id"],
            purpose=EmailOTP.PASSWORD_RESET,
            is_used=True,
        )
    except (EmailOTP.DoesNotExist, KeyError) as exc:
        raise serializers.ValidationError("Invalid or expired reset token.") from exc

    if otp.expires_at <= timezone.now():
        raise serializers.ValidationError("Invalid or expired reset token.")
    return otp
