from bson import ObjectId
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .mongo import user_collection, user_otp_collection
from user_domain.schema import UserSchema, UserOTPSchema
from .utils import (
    generate_jwt,
    generate_otp,
    normalize_email,
    otp_expiry_time,
    send_email_otp,
    user_response,
)


@method_decorator(csrf_exempt, name="dispatch")
class UserRegisterView(APIView):
    """
    API endpoint for user registration
    POST /api/user/auth/register/
    Body: {full_name, email, password, role}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validate required fields
        required_fields = ["full_name", "email", "password"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return Response(
                {"error": f"Missing fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = normalize_email(data["email"])
        full_name = data["full_name"].strip()
        password = data["password"]
        role = data.get("role", "member")
        phone_number = data.get("phone_number")

        # Check if user already exists
        existing_user = user_collection.find_one({"email": email})
        if existing_user:
            return Response(
                {"error": "User with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Hash password
        password_hash = make_password(password)

        # Create user document
        user_doc = UserSchema.create_user(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            role=role,
            phone_number=phone_number,
        )

        # Insert into database
        result = user_collection.insert_one(user_doc)
        user_id = str(result.inserted_id)

        # Generate OTP for email verification
        otp_code = generate_otp()
        expiry = otp_expiry_time()
        otp_doc = UserOTPSchema.create_otp(user_id, email, otp_code, expiry)
        user_otp_collection.insert_one(otp_doc)

        # Send OTP email
        send_email_otp(email, otp_code)

        # Generate JWT token
        token = generate_jwt(user_id, email)

        # Get user document for response
        user_doc = user_collection.find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "User registered successfully. Please verify your email.",
                "token": token,
                "user": user_response(user_doc),
                "otp_sent": True,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class UserLoginView(APIView):
    """
    API endpoint for user login
    POST /api/user/auth/login/
    Body: {email, password}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = normalize_email(data.get("email", ""))
        password = data.get("password", "")

        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find user
        user = user_collection.find_one({"email": email})
        if not user:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check password
        if not check_password(password, user["password"]):
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check if user is active
        if not user.get("is_active", True):
            return Response(
                {"error": "Account is deactivated"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Update last login
        user_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": timezone.now()}},
        )

        # Generate JWT token
        token = generate_jwt(str(user["_id"]), email)

        return Response(
            {
                "message": "Login successful",
                "token": token,
                "user": user_response(user),
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class VerifyOTPView(APIView):
    """
    API endpoint to verify OTP
    POST /api/user/auth/verify-otp/
    Body: {email, otp}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = normalize_email(data.get("email", ""))
        otp = data.get("otp", "")

        if not email or not otp:
            return Response(
                {"error": "Email and OTP are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find OTP record
        otp_record = user_otp_collection.find_one(
            {"email": email, "otp": otp, "is_used": False}
        )

        if not otp_record:
            return Response(
                {"error": "Invalid or expired OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if OTP is expired
        if timezone.now() > otp_record["expiry"]:
            return Response(
                {"error": "OTP has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP as used
        user_otp_collection.update_one(
            {"_id": otp_record["_id"]},
            {"$set": {"is_used": True}},
        )

        # Mark user as verified
        user_collection.update_one(
            {"_id": otp_record["user_id"]},
            {"$set": {"is_verified": True}},
        )

        # Get updated user
        user = user_collection.find_one({"_id": otp_record["user_id"]})

        return Response(
            {
                "message": "Email verified successfully",
                "user": user_response(user),
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ResendOTPView(APIView):
    """
    API endpoint to resend OTP
    POST /api/user/auth/resend-otp/
    Body: {email}
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        email = normalize_email(data.get("email", ""))

        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find user
        user = user_collection.find_one({"email": email})
        if not user:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if already verified
        if user.get("is_verified", False):
            return Response(
                {"error": "Email is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate new OTP
        otp_code = generate_otp()
        expiry = otp_expiry_time()
        otp_doc = UserOTPSchema.create_otp(str(user["_id"]), email, otp_code, expiry)
        user_otp_collection.insert_one(otp_doc)

        # Send OTP email
        send_email_otp(email, otp_code)

        return Response(
            {"message": "OTP sent successfully"},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class UserProfileView(APIView):
    """
    API endpoint to get/update user profile
    GET /api/user/auth/profile/
    PUT /api/user/auth/profile/
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        # Get user_id from request (from JWT token in real implementation)
        user_id = request.GET.get("user_id")
        
        if not user_id:
            return Response(
                {"error": "User ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = user_collection.find_one({"_id": ObjectId(user_id)})
        except:
            return Response(
                {"error": "Invalid user ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"user": user_response(user)},
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        # Get user_id from request
        user_id = request.data.get("user_id")
        
        if not user_id:
            return Response(
                {"error": "User ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Allowed fields for update
        allowed_fields = [
            "full_name", "phone_number", "profile_image", "date_of_birth",
            "gender", "address", "city", "state", "pincode",
            "emergency_contact", "fitness_goals", "preferred_workout_time"
        ]

        # Build update document
        updates = {}
        for field in allowed_fields:
            if field in request.data:
                updates[field] = request.data[field]

        if not updates:
            return Response(
                {"error": "No valid fields to update"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add updated_at timestamp
        updates = UserSchema.update_user(updates)

        # Update user
        try:
            result = user_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": updates}
            )
        except:
            return Response(
                {"error": "Invalid user ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if result.matched_count == 0:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get updated user
        user = user_collection.find_one({"_id": ObjectId(user_id)})

        return Response(
            {
                "message": "Profile updated successfully",
                "user": user_response(user),
            },
            status=status.HTTP_200_OK,
        )
