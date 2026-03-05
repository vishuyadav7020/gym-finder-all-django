from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from bson import ObjectId
from datetime import datetime
from django.utils import timezone
import jwt
from django.conf import settings

from .mongo import org_payment_collection
from ..member.mongo import org_member_collection
from ..gym.mongo import org_gym_collection
from ..schema import MemberSchema, PaymentSchema
from user_domain.authentication.mongo import user_collection


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


def payment_response(doc: dict) -> dict:
    """Format payment document for API response"""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at", "payment_date"):
        if key in doc and doc[key]:
            doc[key] = doc[key].isoformat() if hasattr(doc[key], "isoformat") else str(doc[key])
    return doc


@method_decorator(csrf_exempt, name="dispatch")
class CreateTrialPaymentView(APIView):
    """
    POST /api/org/payment/trial/
    Create payment and membership directly for trial plans (1 day, 2 days)
    Bypasses approval process
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        required = ["gym_id", "user_name", "user_email", "plan_name", "price", "plan_duration"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

        user_id = get_user_from_token(request)
        if not user_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Get gym details to find owner_id
        try:
            gym = org_gym_collection.find_one({"_id": ObjectId(data["gym_id"])})
        except Exception:
            return Response({"error": "Invalid gym ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not gym:
            return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)
        
        owner_id = gym.get("owner_id")
        gym_name = gym.get("gym_name", "")

        # Create the membership directly (no approval needed for trial)
        member_doc = MemberSchema.create_member(
            owner_id=owner_id,
            gym_id=data["gym_id"],
            gym_name=gym_name,
            user_name=data["user_name"],
            user_email=data["user_email"],
            plan_name=data["plan_name"],
            price=float(data["price"]),
            plan_duration=data["plan_duration"],
        )
        member_result = org_member_collection.insert_one(member_doc)
        member_id = str(member_result.inserted_id)
        
        # Update gym member count
        org_gym_collection.update_one(
            {"_id": ObjectId(data["gym_id"])},
            {
                "$inc": {"total_members": 1},
                "$push": {"members": member_id},
                "$set": {"updated_at": timezone.now()}
            },
        )

        # Update user's gym_memberships array
        user_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$addToSet": {"gym_memberships": data["gym_id"]},
                "$set": {"updated_at": timezone.now()}
            },
        )

        # Create the payment record
        payment_doc = PaymentSchema.create_payment(
            owner_id=owner_id,
            membership_id=member_id,
            gym_id=data["gym_id"],
            gym_name=gym_name,
            member_name=data["user_name"],
            plan_name=data["plan_name"],
            amount=float(data["price"]),
            payment_method=data.get("payment_method", "cash"),
            notes=data.get("notes"),
        )

        result = org_payment_collection.insert_one(payment_doc)
        payment_doc["_id"] = str(result.inserted_id)

        return Response(
            {
                "message": "Trial membership activated successfully",
                "payment": payment_response(payment_doc),
                "membership_id": member_id,
            },
            status=status.HTTP_201_CREATED,
        )
