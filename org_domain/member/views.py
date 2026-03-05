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

from .mongo import org_member_collection, org_membership_request_collection
from org_domain.authentication.mongo import org_collection
from org_domain.gym.mongo import org_gym_collection
from user_domain.authentication.mongo import user_collection
from org_domain.schema import MemberSchema, MembershipRequestSchema


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


def get_user_from_token(request):
    """Extract user_id from JWT token in Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        # Try to get user_id first (for regular users), then owner_id (for gym owners)
        return payload.get("user_id") or payload.get("owner_id")
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


def request_response(doc: dict) -> dict:
    """Format membership request document for API response"""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at"):
        if key in doc and doc[key]:
            doc[key] = doc[key].isoformat() if hasattr(doc[key], "isoformat") else str(doc[key])
    return doc


# ──────────────────────────── MEMBER CRUD ────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class CreateMemberView(APIView):
    """POST /api/org/member/create/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        required = ["gym_id", "user_name", "plan_name", "price"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify gym exists and belongs to owner
        try:
            gym = org_gym_collection.find_one({"_id": ObjectId(data["gym_id"])})
        except Exception:
            return Response({"error": "Invalid gym ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not gym:
            return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)
        if gym.get("owner_id") != owner_id:
            return Response({"error": "You don't own this gym"}, status=status.HTTP_403_FORBIDDEN)

        member_doc = MemberSchema.create_member(
            owner_id=owner_id,
            gym_id=data["gym_id"],
            gym_name=gym.get("gym_name", ""),
            user_name=data["user_name"],
            user_email=data.get("user_email"),
            plan_name=data["plan_name"],
            price=float(data["price"]),
            duration_months=int(data.get("duration_months", 1)),
        )

        result = org_member_collection.insert_one(member_doc)
        member_id = str(result.inserted_id)
        member_doc["_id"] = member_id

        # Update gym member count and add member to members array
        org_gym_collection.update_one(
            {"_id": ObjectId(data["gym_id"])},
            {
                "$inc": {"total_members": 1},
                "$push": {"members": member_id},
                "$set": {"updated_at": timezone.now()}
            },
        )

        return Response(
            {"message": "Member registered successfully", "member": member_response(member_doc)},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ListMembersView(APIView):
    """GET /api/org/member/list/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        members = list(org_member_collection.find({"owner_id": owner_id}).sort("created_at", -1))
        return Response(
            {"members": [member_response(m) for m in members]},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class UpdateMemberView(APIView):
    """PUT /api/org/member/update/<member_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def put(self, request, member_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            member = org_member_collection.find_one({"_id": ObjectId(member_id)})
        except Exception:
            return Response({"error": "Invalid member ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        if member.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        allowed_fields = ["user_name", "user_email", "plan_name", "price", "status", "end_date"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        update_data["updated_at"] = timezone.now()

        org_member_collection.update_one({"_id": ObjectId(member_id)}, {"$set": update_data})
        updated = org_member_collection.find_one({"_id": ObjectId(member_id)})
        return Response(
            {"message": "Member updated successfully", "member": member_response(updated)},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class DeleteMemberView(APIView):
    """DELETE /api/org/member/delete/<member_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def delete(self, request, member_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            member = org_member_collection.find_one({"_id": ObjectId(member_id)})
        except Exception:
            return Response({"error": "Invalid member ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        if member.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        org_member_collection.delete_one({"_id": ObjectId(member_id)})

        # Decrement gym member count and remove member from members array
        try:
            org_gym_collection.update_one(
                {"_id": ObjectId(member["gym_id"])},
                {
                    "$inc": {"total_members": -1},
                    "$pull": {"members": member_id},
                    "$set": {"updated_at": timezone.now()}
                },
            )
        except Exception:
            pass

        return Response({"message": "Member deleted successfully"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class RenewMemberView(APIView):
    """POST /api/org/member/renew/<member_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, member_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            member = org_member_collection.find_one({"_id": ObjectId(member_id)})
        except Exception:
            return Response({"error": "Invalid member ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)
        if member.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        duration = int(request.data.get("duration_months", member.get("duration_months", 1)))
        import datetime as dt
        new_start = timezone.now()
        new_end = new_start + dt.timedelta(days=30 * duration)

        org_member_collection.update_one(
            {"_id": ObjectId(member_id)},
            {"$set": {
                "status": "active",
                "start_date": new_start,
                "end_date": new_end,
                "duration_months": duration,
                "updated_at": timezone.now(),
            }},
        )

        updated = org_member_collection.find_one({"_id": ObjectId(member_id)})
        return Response(
            {"message": "Membership renewed", "member": member_response(updated)},
            status=status.HTTP_200_OK,
        )


# ──────────────────── MEMBERSHIP REQUESTS ────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class CreateMembershipRequestView(APIView):
    """POST /api/org/member/request/create/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        required = ["gym_id", "plan_name", "price"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            gym = org_gym_collection.find_one({"_id": ObjectId(data["gym_id"])})
        except Exception:
            return Response({"error": "Invalid gym ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not gym:
            return Response({"error": "Gym not found"}, status=status.HTTP_404_NOT_FOUND)

        # Try to get user_id from JWT token
        user_id = get_user_from_token(request)
        
        # If user is logged in, get their details from user_collection
        user_name = data.get("user_name")
        user_email = data.get("user_email")
        
        if user_id:
            try:
                user = user_collection.find_one({"_id": ObjectId(user_id)})
                if user:
                    user_name = user.get("full_name") or user_name
                    user_email = user.get("email") or user_email
            except:
                pass  # If user lookup fails, use provided data

        req_doc = MembershipRequestSchema.create_request(
            gym_id=data["gym_id"],
            gym_name=gym.get("gym_name", ""),
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            plan_name=data["plan_name"],
            price=float(data["price"]),
            message=data.get("message"),
        )

        result = org_membership_request_collection.insert_one(req_doc)
        req_doc["_id"] = str(result.inserted_id)
        return Response(
            {"message": "Request submitted", "request": request_response(req_doc)},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ListMembershipRequestsView(APIView):
    """GET /api/org/member/request/list/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Get all gym IDs owned by this owner
        owner_gyms = list(org_gym_collection.find({"owner_id": owner_id}, {"_id": 1}))
        gym_ids = [str(g["_id"]) for g in owner_gyms]

        requests_list = list(
            org_membership_request_collection.find({"gym_id": {"$in": gym_ids}}).sort("created_at", -1)
        )
        
        # Populate user details for each request
        for req in requests_list:
            if req.get("user_id"):
                try:
                    user = user_collection.find_one({"_id": ObjectId(req["user_id"])})
                    if user:
                        req["user_details"] = {
                            "_id": str(user["_id"]),
                            "full_name": user.get("full_name"),
                            "email": user.get("email"),
                            "phone_number": user.get("phone_number"),
                            "profile_image": user.get("profile_image"),
                        }
                except:
                    pass  # If user lookup fails, skip user_details
        
        return Response(
            {"requests": [request_response(r) for r in requests_list]},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ListUserMembershipRequestsView(APIView):
    """GET /api/org/member/request/user/<user_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, user_id):
        # Get all membership requests for this user
        try:
            requests_list = list(
                org_membership_request_collection.find({"user_id": user_id}).sort("created_at", -1)
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch requests: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"requests": [request_response(r) for r in requests_list]},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class UpdateMembershipRequestView(APIView):
    """PUT /api/org/member/request/update/<request_id>/"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def put(self, request, request_id):
        owner_id = get_owner_from_token(request)
        if not owner_id:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            req_doc = org_membership_request_collection.find_one({"_id": ObjectId(request_id)})
        except Exception:
            return Response({"error": "Invalid request ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not req_doc:
            return Response({"error": "Request not found"}, status=status.HTTP_404_NOT_FOUND)

        # Verify the gym belongs to this owner
        try:
            gym = org_gym_collection.find_one({"_id": ObjectId(req_doc["gym_id"])})
        except Exception:
            gym = None
        if not gym or gym.get("owner_id") != owner_id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        if new_status not in ("approved", "rejected"):
            return Response({"error": "Status must be 'approved' or 'rejected'"}, status=status.HTTP_400_BAD_REQUEST)

        org_membership_request_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {"status": new_status, "updated_at": timezone.now()}},
        )

        # Note: Membership will be created only after payment is made
        # No auto-creation of membership on approval

        updated = org_membership_request_collection.find_one({"_id": ObjectId(request_id)})
        return Response(
            {"message": f"Request {new_status}", "request": request_response(updated)},
            status=status.HTTP_200_OK,
        )
