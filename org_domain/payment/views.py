from bson import ObjectId
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

import jwt
from django.conf import settings

from .mongo import org_payment_collection
from org_domain.member.mongo import org_member_collection, org_membership_request_collection
from org_domain.gym.mongo import org_gym_collection
from org_domain.schema import PaymentSchema, MemberSchema


def get_owner_from_token(request):
    """Extract owner_id from JWT token in Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("owner_id")
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
class CreatePaymentView(APIView):
    """POST /api/org/payment/create/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        required = ["membership_id", "amount"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

        # membership_id here is actually the membership request ID
        request_id = data["membership_id"]
        
        # Find the membership request
        try:
            req_doc = org_membership_request_collection.find_one({"_id": ObjectId(request_id)})
        except Exception:
            return Response({"error": "Invalid request ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not req_doc:
            return Response({"error": "Membership request not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Verify the request is approved
        if req_doc.get("status") != "approved":
            return Response({"error": "Membership request must be approved before payment"}, status=status.HTTP_400_BAD_REQUEST)

        # Get gym details to find owner_id
        try:
            gym = org_gym_collection.find_one({"_id": ObjectId(req_doc["gym_id"])})
        except Exception:
            return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if not gym:
            return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)
        
        owner_id = gym.get("owner_id")

        # Create the membership first
        member_doc = MemberSchema.create_member(
            owner_id=owner_id,
            gym_id=req_doc["gym_id"],
            gym_name=req_doc.get("gym_name", ""),
            user_name=req_doc.get("user_name", ""),
            user_email=req_doc.get("user_email"),
            plan_name=req_doc["plan_name"],
            price=float(req_doc["price"]),
        )
        member_result = org_member_collection.insert_one(member_doc)
        member_id = str(member_result.inserted_id)
        
        # Update gym member count
        org_gym_collection.update_one(
            {"_id": ObjectId(req_doc["gym_id"])},
            {
                "$inc": {"total_members": 1},
                "$push": {"members": member_id},
                "$set": {"updated_at": timezone.now()}
            },
        )
        
        # Mark the request as paid
        org_membership_request_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {"paid": True, "membership_id": member_id, "updated_at": timezone.now()}},
        )

        # Now create the payment record
        payment_doc = PaymentSchema.create_payment(
            owner_id=owner_id,
            membership_id=member_id,
            gym_id=req_doc["gym_id"],
            gym_name=req_doc.get("gym_name", ""),
            member_name=req_doc.get("user_name", ""),
            plan_name=req_doc["plan_name"],
            amount=float(data["amount"]),
            payment_method=data.get("payment_method", "cash"),
            notes=data.get("notes"),
        )

        result = org_payment_collection.insert_one(payment_doc)
        payment_doc["_id"] = str(result.inserted_id)

        return Response(
            {
                "message": "Payment recorded and membership created successfully",
                "payment": payment_response(payment_doc),
                "membership_id": member_id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ListPaymentsView(APIView):
    """GET /api/org/payment/list/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        payments = list(org_payment_collection.find({"owner_id": owner_id}).sort("payment_date", -1))
        return Response(
            {"payments": [payment_response(p) for p in payments]},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GetPaymentView(APIView):
    """GET /api/org/payment/<payment_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, payment_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payment = org_payment_collection.find_one({"_id": ObjectId(payment_id)})
        except Exception:
            return Response({"error": "Invalid payment ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not payment:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        if payment.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        return Response({"payment": payment_response(payment)}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class UpdatePaymentView(APIView):
    """PUT /api/org/payment/update/<payment_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def put(self, request, payment_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payment = org_payment_collection.find_one({"_id": ObjectId(payment_id)})
        except Exception:
            return Response({"error": "Invalid payment ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not payment:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        if payment.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        allowed_fields = ["amount", "payment_method", "status", "notes"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data["updated_at"] = timezone.now()

        org_payment_collection.update_one({"_id": ObjectId(payment_id)}, {"$set": update_data})
        updated = org_payment_collection.find_one({"_id": ObjectId(payment_id)})
        return Response(
            {"message": "Payment updated successfully", "payment": payment_response(updated)},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class DeletePaymentView(APIView):
    """DELETE /api/org/payment/delete/<payment_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def delete(self, request, payment_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payment = org_payment_collection.find_one({"_id": ObjectId(payment_id)})
        except Exception:
            return Response({"error": "Invalid payment ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not payment:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        if payment.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        org_payment_collection.delete_one({"_id": ObjectId(payment_id)})
        return Response({"message": "Payment deleted successfully"}, status=status.HTTP_200_OK)
