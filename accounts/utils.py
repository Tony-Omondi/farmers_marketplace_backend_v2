"""
accounts/utils.py - Email Utility Functions

This module contains utility functions for sending OTP emails for user registration
and password reset purposes in a Django application.
"""

from django.core.mail import send_mail
from django.conf import settings
from typing import Literal

def send_otp_email(to_email: str, code: str, purpose: Literal["register", "reset"]) -> None:
    """
    Send an OTP (One-Time Password) email to the user for verification or password reset.
    
    Args:
        to_email (str): The recipient's email address
        code (str): The OTP code to send
        purpose (str): Either "register" for account verification or "reset" for password reset
        
    Returns:
        None
        
    Raises:
        SMTPException: If there's an error sending the email
    """
    
    # Email content configuration
    email_templates = {
        "register": {
            "subject": "🔐 Verify Your Account",
            "message": f"""
            Welcome to our platform! 

            Your verification code is: 
            🎯 {code} 
            
            ⏳ This code will expire in 15 minutes.
            
            If you didn't request this, please ignore this email.
            
            Best regards,
            The {settings.SITE_NAME} Team
            """
        },
        "reset": {
            "subject": "🔑 Password Reset Request",
            "message": f"""
            We received a request to reset your password.
            
            Your reset code is:
            🎯 {code}
            
            ⏳ This code will expire in 15 minutes.
            
            If you didn't request this, please secure your account.
            
            Best regards,
            The {settings.SITE_NAME} Team
            """
        }
    }
    
    # Get the appropriate template based on purpose
    template = email_templates.get(purpose)
    if not template:
        raise ValueError(f"Invalid purpose: {purpose}. Must be 'register' or 'reset'.")
    
    # Send the email
    send_mail(
        subject=template["subject"],
        message=template["message"].strip(),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[to_email],
        fail_silently=False,
    )