from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from bson import ObjectId
from django.utils import timezone
import jwt
from django.conf import settings

from .mongo import user_collection
from org_domain.gym.mongo import org_gym_collection


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


@method_decorator(csrf_exempt, name="dispatch")
class ToggleFavoriteGymView(APIView):
    """
    POST /api/user/auth/favorite/toggle/
    Add or remove a gym from user's favorite_gyms array
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        gym_id = request.data.get("gym_id")
        if not gym_id:
            return Response({"error": "gym_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get user document
            user = user_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check if gym exists
            gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})
            if not gym:
                return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)

            # Get current favorite_gyms array
            favorite_gyms = user.get("favorite_gyms", [])

            # Toggle favorite
            if gym_id in favorite_gyms:
                # Remove from favorites
                user_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$pull": {"favorite_gyms": gym_id},
                        "$set": {"updated_at": timezone.now()}
                    }
                )
                is_favorite = False
                message = "Gym removed from favorites"
            else:
                # Add to favorites
                user_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$addToSet": {"favorite_gyms": gym_id},
                        "$set": {"updated_at": timezone.now()}
                    }
                )
                is_favorite = True
                message = "Gym added to favorites"

            return Response(
                {
                    "message": message,
                    "is_favorite": is_favorite,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class GetFavoriteGymsView(APIView):
    """
    GET /api/user/auth/favorite/list/
    Get all favorite gyms for the current user
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Get user document
            user = user_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Get favorite gym IDs
            favorite_gym_ids = user.get("favorite_gyms", [])

            # Fetch gym details for each favorite
            gyms = []
            for gym_id in favorite_gym_ids:
                try:
                    gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})
                    if gym:
                        gym["_id"] = str(gym["_id"])
                        # Format dates
                        for key in ("created_at", "updated_at"):
                            if key in gym and gym[key]:
                                gym[key] = gym[key].isoformat() if hasattr(gym[key], "isoformat") else str(gym[key])
                        gyms.append(gym)
                except Exception:
                    continue

            return Response(
                {
                    "gyms": gyms,
                    "count": len(gyms),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class CheckFavoriteStatusView(APIView):
    """
    GET /api/user/auth/favorite/check/<gym_id>/
    Check if a gym is in user's favorites
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, gym_id):
        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"is_favorite": False}, status=status.HTTP_200_OK)

        try:
            user = user_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return Response({"is_favorite": False}, status=status.HTTP_200_OK)

            favorite_gyms = user.get("favorite_gyms", [])
            is_favorite = gym_id in favorite_gyms

            return Response({"is_favorite": is_favorite}, status=status.HTTP_200_OK)

        except Exception:
            return Response({"is_favorite": False}, status=status.HTTP_200_OK)
