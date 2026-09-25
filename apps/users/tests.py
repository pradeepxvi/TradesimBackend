from datetime import timedelta
from io import BytesIO

from django.db import IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from .models import EmailOTP, User


class UserModelTests(TestCase):
    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email="  Trader@Example.COM ",
            password="test-password",
        )

        self.assertEqual(user.email, "trader@example.com")
        self.assertTrue(user.check_password("test-password"))
        self.assertFalse(user.is_staff)

    def test_email_must_be_unique(self):
        User.objects.create_user("trader@example.com", "test-password")

        with self.assertRaises(IntegrityError):
            User.objects.create_user("TRADER@example.com", "other-password")

    def test_create_superuser_sets_required_flags(self):
        user = User.objects.create_superuser("admin@example.com", "test-password")

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)


class EmailOTPModelTests(TestCase):
    def test_otp_belongs_to_user(self):
        user = User.objects.create_user("trader@example.com", "test-password")
        otp = EmailOTP.objects.create(
            user=user,
            otp="123456",
            purpose=EmailOTP.REGISTRATION_VERIFICATION,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        self.assertEqual(otp.user, user)
        self.assertIn(otp, user.email_otps.all())

    def test_otp_expiration_fields_are_stored(self):
        expires_at = timezone.now() + timedelta(minutes=10)
        otp = EmailOTP.objects.create(
            user=User.objects.create_user("trader@example.com", "test-password"),
            otp="123456",
            purpose=EmailOTP.PASSWORD_RESET,
            expires_at=expires_at,
        )

        self.assertEqual(otp.expires_at, expires_at)
        self.assertFalse(otp.is_used)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationAPITests(APITestCase):
    password = "StrongPass123!"
    email = "trader@example.com"

    def register(self):
        return self.client.post(
            "/api/v1/auth/register/",
            {
                "email": self.email,
                "password": self.password,
                "password_confirmation": self.password,
                "full_name": "Test Trader",
            },
            format="json",
        )

    def create_verified_user(self):
        user = User.objects.create_user(self.email, self.password)
        user.is_verified = True
        user.save(update_fields=["is_verified"])
        return user

    def test_registration_creates_unverified_user_and_sends_otp(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("otp", response.data)
        self.assertFalse(User.objects.get(email=self.email).is_verified)
        self.assertEqual(EmailOTP.objects.count(), 1)

    def test_duplicate_email_is_rejected(self):
        self.register()

        response = self.register()

        self.assertEqual(response.status_code, 400)

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": self.email,
                "password": "short",
                "password_confirmation": "short",
                "full_name": "Test Trader",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_otp_verification_activates_user(self):
        self.register()
        otp = EmailOTP.objects.get()

        response = self.client.post(
            "/api/v1/auth/verify-otp/",
            {"email": self.email, "otp": otp.otp},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.email)
        self.assertTrue(user.is_verified)
        self.assertTrue(user.is_active)
        self.assertTrue(EmailOTP.objects.get(pk=otp.pk).is_used)

    def test_expired_otp_is_rejected(self):
        self.register()
        otp = EmailOTP.objects.get()
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=["expires_at"])

        response = self.client.post(
            "/api/v1/auth/verify-otp/",
            {"email": self.email, "otp": otp.otp},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_used_otp_is_rejected(self):
        self.register()
        otp = EmailOTP.objects.get()
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        response = self.client.post(
            "/api/v1/auth/verify-otp/",
            {"email": self.email, "otp": otp.otp},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_resend_otp_invalidates_previous_code(self):
        self.register()
        first_otp = EmailOTP.objects.get()

        response = self.client.post(
            "/api/v1/auth/resend-otp/",
            {"email": self.email},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmailOTP.objects.get(pk=first_otp.pk).is_used)
        self.assertEqual(
            EmailOTP.objects.filter(
                user__email=self.email,
                purpose=EmailOTP.REGISTRATION_VERIFICATION,
                is_used=False,
            ).count(),
            1,
        )

    def test_unverified_user_cannot_login(self):
        User.objects.create_user(self.email, self.password)

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_login_returns_tokens_and_refresh_works(self):
        self.create_verified_user()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    def test_authenticated_user_can_change_password(self):
        self.create_verified_user()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.email, "password": self.password},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": self.password,
                "new_password": "NewStrongPass123!",
                "confirm_password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.get(email=self.email).check_password("NewStrongPass123!")
        )

    def test_password_reset_otp_can_reset_password_once(self):
        user = self.create_verified_user()
        self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"email": self.email},
            format="json",
        )
        otp = EmailOTP.objects.get(user=user, purpose=EmailOTP.PASSWORD_RESET)
        verify_response = self.client.post(
            "/api/v1/auth/password-reset/verify-otp/",
            {"email": self.email, "otp": otp.otp},
            format="json",
        )

        reset_data = {
            "reset_token": verify_response.data["reset_token"],
            "new_password": "ResetStrongPass123!",
            "confirm_password": "ResetStrongPass123!",
        }
        reset_response = self.client.post(
            "/api/v1/auth/password-reset/",
            reset_data,
            format="json",
        )
        replay_response = self.client.post(
            "/api/v1/auth/password-reset/",
            {
                **reset_data,
                "new_password": "AnotherStrongPass123!",
                "confirm_password": "AnotherStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(replay_response.status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.check_password("ResetStrongPass123!"))


class ProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "profile@example.com",
            "StrongPass123!",
            full_name="Original Name",
        )
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])
        self.client.force_authenticate(self.user)

    def test_anonymous_profile_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/profile/")

        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_retrieve_profile(self):
        response = self.client.get("/api/v1/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "profile@example.com")
        self.assertEqual(response.data["full_name"], "Original Name")
        self.assertNotIn("password", response.data)
        self.assertNotIn("pending_email", response.data)

    def test_user_can_update_full_name(self):
        response = self.client.patch(
            "/api/v1/profile/",
            {"full_name": "Updated Name"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Updated Name")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_update_requires_verification(self):
        response = self.client.patch(
            "/api/v1/profile/",
            {"email": "new@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertEqual(self.user.pending_email, "new@example.com")
        otp = EmailOTP.objects.get(
            user=self.user,
            purpose=EmailOTP.EMAIL_CHANGE,
        )

        response = self.client.post(
            "/api/v1/profile/verify-email-change/",
            {"email": "new@example.com", "otp": otp.otp},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertIsNone(self.user.pending_email)

    def test_valid_profile_picture_upload(self):
        image = Image.new("RGB", (10, 10), color="red")
        image_file = BytesIO()
        image.save(image_file, format="PNG")
        image_file.seek(0)

        response = self.client.patch(
            "/api/v1/profile/",
            {
                "profile_picture": SimpleUploadedFile(
                    "profile.png",
                    image_file.getvalue(),
                    content_type="image/png",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["profile_picture"])

    def test_invalid_profile_picture_is_rejected(self):
        response = self.client.patch(
            "/api/v1/profile/",
            {
                "profile_picture": (
                    "profile.txt",
                    BytesIO(b"not an image"),
                    "text/plain",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)

    def test_existing_password_change_endpoint_still_works(self):
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": "StrongPass123!",
                "new_password": "NewStrongPass123!",
                "confirm_password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass123!"))
