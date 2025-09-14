# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmailOTP

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("email", "full_name", "is_active", "is_staff", "date_joined")
    ordering = ("email",)
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2", "is_active", "is_staff", "is_superuser"),
        }),
    )
    filter_horizontal = ("groups", "user_permissions",)

@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "code", "is_used", "created_at", "expires_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("email", "code")
