from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from bson import ObjectId
import jwt
from django.conf import settings

from .mongo import user_collection


def get_user_from_token(request):
    """Extract user_id from JWT token in Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        return None


def user_response(doc: dict) -> dict:
    """Format user document for API response"""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    # Remove sensitive fields
    doc.pop("password", None)
    # Format dates
    for key in ("created_at", "updated_at", "last_login", "date_of_birth"):
        if key in doc and doc[key]:
            doc[key] = doc[key].isoformat() if hasattr(doc[key], "isoformat") else str(doc[key])
    return doc


@method_decorator(csrf_exempt, name="dispatch")
class UserProfileView(APIView):
    """GET/PUT /api/user/profile/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """Get current user's profile"""
        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user_doc = user_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return Response({"error": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not user_doc:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"user": user_response(user_doc)}, status=status.HTTP_200_OK)

    def put(self, request):
        """Update current user's profile"""
        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user_doc = user_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return Response({"error": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not user_doc:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get update data from request
        data = request.data
        update_fields = {}

        # Allow updating these fields
        allowed_fields = [
            "full_name", "phone_number", "address", "gender", 
            "date_of_birth", "emergency_contact", "fitness_goals",
            "profile_image", "city", "state", "pincode"
        ]

        for field in allowed_fields:
            if field in data:
                update_fields[field] = data[field]

        if not update_fields:
            return Response({"error": "No valid fields to update"}, status=status.HTTP_400_BAD_REQUEST)

        # Update user document
        from datetime import datetime
        update_fields["updated_at"] = datetime.utcnow()

        user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_fields}
        )

        # Fetch updated user
        updated_user = user_collection.find_one({"_id": ObjectId(user_id)})

        return Response(
            {"message": "Profile updated successfully", "user": user_response(updated_user)},
            status=status.HTTP_200_OK
        )
