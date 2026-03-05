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


def generate_jwt(owner_id: str, email: str) -> str:
    """Generate JWT token for gym owner"""
    refresh = RefreshToken()
    refresh["owner_id"] = str(owner_id)
    refresh["email"] = email
    return str(refresh.access_token)


def otp_expiry_time():
    """Get OTP expiry time (10 minutes from now)"""
    return timezone.now() + timedelta(minutes=10)


def normalize_email(email: str) -> str:
    """Normalize email to lowercase"""
    return email.strip().lower()


def gym_owner_response(owner_doc: dict) -> dict:
    """Format gym owner document for API response (remove sensitive data)"""
    if not owner_doc:
        return {}
    owner_doc = dict(owner_doc)
    if "_id" in owner_doc:
        owner_doc["_id"] = str(owner_doc["_id"])

    # Convert gym ObjectIds to strings for JSON serialization
    if "gyms" in owner_doc and isinstance(owner_doc["gyms"], list):
        owner_doc["gyms"] = [str(gid) for gid in owner_doc["gyms"]]

    owner_doc.pop("password", None)
    return owner_doc
