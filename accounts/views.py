# accounts/views.py
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status, permissions, views, generics
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import EmailOTP
from .serializers import (
    RegisterSerializer, VerifyOTPSerializer, LoginSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer
)
from .utils import send_otp_email
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def issue_tokens_for_user(user: User):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        otp = EmailOTP.objects.filter(email=user.email, purpose=EmailOTP.PURPOSE_REGISTER, is_used=False).order_by("-created_at").first()
        if otp:
            send_otp_email(user.email, otp.code, purpose=EmailOTP.PURPOSE_REGISTER)

class VerifyOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        code = serializer.validated_data["code"]

        otp = EmailOTP.objects.filter(email=email, code=code, is_used=False).order_by("-created_at").first()
        if not otp:
            return Response({"detail": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.expires_at < timezone.now():
            return Response({"detail": "Code expired"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user.is_active = True
        user.save()
        otp.is_used = True
        otp.save()

        tokens = issue_tokens_for_user(user)
        return Response({"message": "Account activated", "tokens": tokens}, status=status.HTTP_200_OK)

class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logger.info(f"Login request data: {request.data}")
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]

        user = authenticate(request, email=email, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "Please verify your email first"}, status=status.HTTP_403_FORBIDDEN)

        tokens = issue_tokens_for_user(user)
        return Response({"message": "Logged in", "tokens": tokens}, status=status.HTTP_200_OK)

class ForgotPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()

        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If the email exists, an OTP has been sent."}, status=status.HTTP_200_OK)

        otp = EmailOTP.objects.create(
            email=email,
            code=''.join(__import__("random").choices("0123456789", k=6)),
            purpose=EmailOTP.PURPOSE_RESET,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        send_otp_email(email, otp.code, purpose=EmailOTP.PURPOSE_RESET)
        return Response({"message": "OTP sent if account exists"}, status=status.HTTP_200_OK)

class ResetPasswordView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        otp = EmailOTP.objects.filter(email=email, code=code, is_used=False, purpose=EmailOTP.PURPOSE_RESET).order_by("-created_at").first()
        if not otp:
            return Response({"detail": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST)
        if otp.expires_at < timezone.now():
            return Response({"detail": "Code expired"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()
        otp.is_used = True
        otp.save()

        return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)

class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        u = request.user
        logger.info(f"Me response for user {u.email}: is_staff={u.is_staff}, is_active={u.is_active}")
        return Response({
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "is_staff": u.is_staff,
            "is_active": u.is_active  # Added is_active
        })