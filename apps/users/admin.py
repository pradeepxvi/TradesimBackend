from django.contrib import admin

from .models import EmailOTP, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "full_name",
        "is_active",
        "is_staff",
        "is_verified",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "is_verified")
    search_fields = ("email", "full_name")
    ordering = ("-date_joined",)


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "is_used", "expires_at", "created_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("user__email", "otp")
    ordering = ("-created_at",)
