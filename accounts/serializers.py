# accounts/serializers.py
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import EmailOTP
from datetime import timedelta

User = get_user_model()

class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        validate_password(data["password"])
        return data

    def create(self, validated_data):
        full_name = validated_data["full_name"]
        email = validated_data["email"].lower()
        password = validated_data["password"]

        # Create user inactive until OTP verify
        user, created = User.objects.get_or_create(email=email, defaults={"full_name": full_name})
        if not created:
            # if user exists and not active, we still can resend OTP; but fail if fully active
            if user.is_active:
                raise serializers.ValidationError({"email": "User already exists and is active"})
            user.full_name = full_name
            user.set_password(password)
            user.save()
        else:
            user.set_password(password)
            user.is_active = False
            user.save()

        # Create OTP
        code = EmailOTP._meta.get_field("code").default() if hasattr(EmailOTP._meta.get_field("code"), "default") else None
        # generate fresh code
        code = ''.join(__import__("random").choices("0123456789", k=6))
        EmailOTP.objects.create(
            email=email,
            code=code,
            purpose=EmailOTP.PURPOSE_REGISTER,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        # Email sending handled in view/util
        return user

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match"})
        validate_password(data["new_password"])
        return data
