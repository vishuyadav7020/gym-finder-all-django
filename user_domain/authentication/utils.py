import logging
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return f"{secrets.randbelow(900000) + 100000}"


def send_email_otp(email: str, otp: str) -> None:
    """Send OTP via email (mock implementation)"""
    logger.info("Mock Email OTP to %s: %s", email, otp)


def generate_jwt(user_id: str, email: str) -> str:
    """Generate JWT token for user"""
    refresh = RefreshToken()
    refresh["user_id"] = str(user_id)
    refresh["email"] = email
    return str(refresh.access_token)


def otp_expiry_time():
    """Get OTP expiry time (10 minutes from now)"""
    return timezone.now() + timedelta(minutes=10)


def normalize_email(email: str) -> str:
    """Normalize email to lowercase"""
    return email.strip().lower()


def user_response(user_doc: dict) -> dict:
    """Format user document for API response (remove sensitive data)"""
    if not user_doc:
        return {}
    user_doc = dict(user_doc)
    if "_id" in user_doc:
        user_doc["_id"] = str(user_doc["_id"])

    # Convert ObjectIds to strings for JSON serialization
    if "gym_memberships" in user_doc and isinstance(user_doc["gym_memberships"], list):
        user_doc["gym_memberships"] = [str(gid) for gid in user_doc["gym_memberships"]]
    
    if "favorite_gyms" in user_doc and isinstance(user_doc["favorite_gyms"], list):
        user_doc["favorite_gyms"] = [str(gid) for gid in user_doc["favorite_gyms"]]

    user_doc.pop("password", None)
    return user_doc
