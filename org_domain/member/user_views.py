from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from bson import ObjectId
import jwt
from django.conf import settings

from .mongo import org_member_collection


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


def member_response(doc: dict) -> dict:
    """Format member document for API response"""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at", "start_date", "end_date"):
        if key in doc and doc[key]:
            doc[key] = doc[key].isoformat() if hasattr(doc[key], "isoformat") else str(doc[key])
    return doc


@method_decorator(csrf_exempt, name="dispatch")
class GetUserMembershipsView(APIView):
    """
    GET /api/org/member/user/<user_id>/
    Get all memberships for a specific user
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        # Verify the requesting user matches the user_id or is authenticated
        requesting_user_id = get_user_from_token(request)
        if not requesting_user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Find all memberships for this user by email
        # Since we store user_email in member documents
        from user_domain.authentication.mongo import user_collection
        
        try:
            user = user_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return Response({"error": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user_email = user.get("email")
        
        # Find all memberships for this user
        memberships = list(org_member_collection.find({"user_email": user_email}))
        
        return Response(
            {
                "memberships": [member_response(m) for m in memberships],
                "count": len(memberships),
            },
            status=status.HTTP_200_OK,
        )
