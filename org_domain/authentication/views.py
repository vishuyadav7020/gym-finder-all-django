from bson import ObjectId
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .mongo import org_collection, org_otp_collection
from org_domain.schema import GymOwnerSchema, GymOwnerOTPSchema
from .utils import (
    generate_jwt,
    generate_otp,
    normalize_email,
    otp_expiry_time,
    send_email_otp,
    gym_owner_response,
)


@method_decorator(csrf_exempt, name="dispatch")
class GymOwnerRegisterView(APIView):
    """
    API endpoint for gym owner registration
    POST /api/org/auth/register/
    Body: {full_name, email, password, role}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validate required fields
        required_fields = ["full_name", "email", "password", "role"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return Response(
                {"error": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate role
        role = data["role"]
        if role not in ("member", "gym_owner"):
            return Response(
                {"error": "role must be 'member' or 'gym_owner'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(data["email"])

        # Validate password length
        if len(data["password"]) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if gym owner already exists
        existing = org_collection.find_one({"email": email})
        if existing:
            if existing.get("is_verified"):
                return Response(
                    {"error": "An account already exists with this email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                # Delete old unverified account to allow re-registration
                org_collection.delete_one({"_id": existing["_id"]})

        # Hash password
        password_hash = make_password(data["password"])

        # Generate OTP for email verification
        otp = generate_otp()

        # Store OTP in database
        org_otp_collection.update_one(
            {"email": email, "purpose": "registration"},
            {
                "$set": {
                    "email": email,
                    "otp": otp,
                    "purpose": "registration",
                    "is_verified": False,
                    "attempts": 0,
                    "expires_at": otp_expiry_time(),
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            },
            upsert=True,
        )

        # Send OTP via email
        send_email_otp(email, otp)

        # Create gym owner document using schema
        owner_doc = GymOwnerSchema.create_gym_owner(
            full_name=data["full_name"],
            email=email,
            role=role,
        )

        # Add password and set initial verification status
        owner_doc["password"] = password_hash
        owner_doc["is_verified"] = False
        owner_doc["status"] = "pending"

        # Insert into database
        result = org_collection.insert_one(owner_doc)
        owner_id = str(result.inserted_id)

        return Response(
            {
                "message": "Registration successful. OTP sent to your email.",
                "owner_id": owner_id,
                "email": email,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class VerifyEmailOtpView(APIView):
    """
    API endpoint to verify email OTP during registration
    POST /api/org/auth/verify-otp/
    Body: {email, otp}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp_input = request.data.get("otp")

        if not email or not otp_input:
            return Response(
                {"error": "email and otp are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Find OTP document
        otp_doc = org_otp_collection.find_one(
            {"email": email, "otp": str(otp_input), "purpose": "registration"}
        )

        if not otp_doc:
            return Response(
                {"error": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if OTP is expired
        expires_at = otp_doc.get("expires_at")
        if expires_at and timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        if expires_at and expires_at < timezone.now():
            org_otp_collection.delete_one({"_id": otp_doc["_id"]})
            return Response(
                {"error": "OTP expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update gym owner verification status
        update_result = org_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "is_verified": True,
                    "status": "verified",
                    "updated_at": timezone.now(),
                }
            },
        )

        if update_result.matched_count == 0:
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Delete OTP
        org_otp_collection.delete_one({"_id": otp_doc["_id"]})

        # Get owner document
        owner = org_collection.find_one({"email": email})

        # Generate JWT token
        token = generate_jwt(str(owner["_id"]), email)

        return Response(
            {
                "message": "Email verified successfully",
                "access": token,
                "owner": gym_owner_response(owner),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ResendOtpView(APIView):
    """
    API endpoint to resend OTP
    POST /api/org/auth/resend-otp/
    Body: {email, purpose}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        purpose = request.data.get("purpose", "registration")

        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Check if account exists for non-registration purposes
        owner = org_collection.find_one({"email": email})
        if not owner and purpose != "registration":
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate new OTP
        otp = generate_otp()

        # Update or create OTP document
        org_otp_collection.update_one(
            {"email": email, "purpose": purpose},
            {
                "$set": {
                    "email": email,
                    "otp": otp,
                    "purpose": purpose,
                    "is_verified": False,
                    "attempts": 0,
                    "expires_at": otp_expiry_time(),
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            },
            upsert=True,
        )

        # Send OTP via email
        send_email_otp(email, otp)

        return Response(
            {"message": "OTP sent successfully to your email."},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GymOwnerLoginView(APIView):
    """
    API endpoint for gym owner login
    POST /api/org/auth/login/
    Body: {email, password}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "email and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Find gym owner by email
        owner_doc = org_collection.find_one({"email": email})

        if not owner_doc:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check if account is verified
        # TODO: Re-enable email verification in production
        # if not owner_doc.get("is_verified"):
        #     return Response(
        #         {"error": "Email not verified. Please complete registration."},
        #         status=status.HTTP_403_FORBIDDEN,
        #     )

        # Check if account is active
        if not owner_doc.get("is_active", True):
            return Response(
                {"error": "Account is inactive. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verify password
        if not check_password(password, owner_doc.get("password", "")):
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generate JWT token
        token = generate_jwt(str(owner_doc["_id"]), email)

        return Response(
            {
                "message": "Login successful",
                "access": token,
                "owner": gym_owner_response(owner_doc),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordView(APIView):
    """
    API endpoint to request password reset OTP
    POST /api/org/auth/forgot-password/
    Body: {email}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Check if account exists
        owner = org_collection.find_one({"email": email})
        if not owner:
            return Response(
                {"error": "No account found with this email"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate OTP
        otp = generate_otp()

        # Store OTP in database
        org_otp_collection.update_one(
            {"email": email, "purpose": "password_reset"},
            {
                "$set": {
                    "email": email,
                    "otp": otp,
                    "purpose": "password_reset",
                    "is_verified": False,
                    "attempts": 0,
                    "expires_at": otp_expiry_time(),
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            },
            upsert=True,
        )

        # Send OTP via email
        send_email_otp(email, otp)

        return Response(
            {"message": "OTP sent to your email for password reset."},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class VerifyForgotPasswordOtpView(APIView):
    """
    API endpoint to verify forgot password OTP
    POST /api/org/auth/verify-forgot-password-otp/
    Body: {email, otp}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp_input = request.data.get("otp")

        if not email or not otp_input:
            return Response(
                {"error": "email and otp are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Find OTP document
        otp_doc = org_otp_collection.find_one(
            {"email": email, "otp": str(otp_input), "purpose": "password_reset"}
        )

        if not otp_doc:
            return Response(
                {"error": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if OTP is expired
        expires_at = otp_doc.get("expires_at")
        if expires_at and timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        if expires_at and expires_at < timezone.now():
            org_otp_collection.delete_one({"_id": otp_doc["_id"]})
            return Response(
                {"error": "OTP expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP as verified (needed for password reset step)
        org_otp_collection.update_one(
            {"_id": otp_doc["_id"]},
            {"$set": {"is_verified": True, "updated_at": timezone.now()}}
        )

        return Response(
            {"message": "OTP verified. You can now reset your password."},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):
    """
    API endpoint to reset password with verified OTP
    POST /api/org/auth/reset-password/
    Body: {email, otp, new_password}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")

        if not email or not otp or not new_password:
            return Response(
                {"error": "email, otp, and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Validate password
        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find verified OTP
        otp_doc = org_otp_collection.find_one(
            {
                "email": email,
                "otp": str(otp),
                "purpose": "password_reset",
                "is_verified": True,
            }
        )

        if not otp_doc:
            return Response(
                {"error": "Invalid or unverified OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if OTP is expired
        expires_at = otp_doc.get("expires_at")
        if expires_at and timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        if expires_at and expires_at < timezone.now():
            org_otp_collection.delete_one({"_id": otp_doc["_id"]})
            return Response(
                {"error": "OTP expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Hash new password
        password_hash = make_password(new_password)

        # Update password
        result = org_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "password": password_hash,
                    "updated_at": timezone.now(),
                }
            },
        )

        if result.matched_count == 0:
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Delete OTP
        org_otp_collection.delete_one({"_id": otp_doc["_id"]})

        return Response(
            {"message": "Password reset successfully"},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GetProfileView(APIView):
    """
    API endpoint to get gym owner profile
    POST /api/org/auth/profile/
    Body: {email}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(email)

        # Find gym owner
        owner = org_collection.find_one({"email": email})
        if not owner:
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "owner": gym_owner_response(owner),
            },
            status=status.HTTP_200_OK,
        )
