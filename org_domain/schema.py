import datetime
from django.utils import timezone
from typing import Dict, List


class BaseSchema:
    @staticmethod
    def timestamps() -> Dict:
        return {
            "created_at": timezone.now(),
            "updated_at": timezone.now()
        }


class GymOwnerSchema(BaseSchema):

    @staticmethod
    def create_gym_owner(
        *,
        full_name: str,
        email: str,
        role: str,  # member, gym_owner
    ) -> Dict:

        return {
            "full_name": full_name,
            "email": email.lower(),
            "role": role,  # member, gym_owner

            # Personal Info
            "phone_number": None,
            "profile_photo": None,
            "date_of_birth": None,
            "gender": None,  # male, female, other

            # Verification
            "status": "pending",  # pending, verified, rejected
            "is_verified": False,
            "is_active": True,

            # Gym Owner specific
            "gyms": [],  # Array of ObjectIds referencing gyms collection

            # Stats
            "total_gyms": 0,
            "total_members": 0,

            **BaseSchema.timestamps()
        }


class GymSchema(BaseSchema):

    @staticmethod
    def create_gym(
        *,
        owner_id: str,
        gym_name: str,
        location: str = "",  # "City, State" for display
        address: str = "",  # Full street address
        phone_number: str = "",
        email: str = None,
        description: str = None,
        image_url: str = None,
        amenities: list = None,
        gym_classification: list = None,  # Array of: basement_local, mid_level, premium, ladies_only, mma_crossfit, yoga_studio
        price_range: str = None,  # $, $$, $$$, $$$$
        website: str = None,
        morning_open: str = None,
        morning_close: str = None,
        evening_open: str = None,
        evening_close: str = None,
    ) -> Dict:

        return {
            "owner_id": owner_id,
            "gym_name": gym_name,
            "location": location,
            "address": address,
            "phone_number": phone_number,
            "email": email,
            "website": website,

            # Details
            "description": description,
            "image_url": image_url,
            "photos": [],  # Array of image URLs
            "logo": None,
            "amenities": amenities or [],
            "gym_classification": gym_classification or [],
            "price_range": price_range,
            "timings": None,  # {open: "06:00", close: "22:00"}
            "morning_open": morning_open,
            "morning_close": morning_close,
            "evening_open": evening_open,
            "evening_close": evening_close,

            # Membership Plans
            "plans": [],  # [{name, duration_days, price, description}]

            # Status
            "status": "active",  # pending, active, inactive
            "is_active": True,

            # Members
            "members": [],  # Array of ObjectIds referencing users
            "total_members": 0,

            # Stats
            "views_count": 0,

            # Ratings
            "rating": None,
            "total_ratings": 0,

            **BaseSchema.timestamps()
        }


class MemberSchema(BaseSchema):

    @staticmethod
    def create_member(
        *,
        owner_id: str,
        gym_id: str,
        gym_name: str,
        user_name: str,
        user_email: str = None,
        plan_name: str,
        price: float,
        plan_duration: str = "monthly",
        duration_months: int = 1,
        start_date=None,
    ) -> Dict:
        start = start_date or timezone.now()
        
        # Calculate end date based on plan_duration
        if plan_duration == "1_day":
            end = start + datetime.timedelta(days=1)
        elif plan_duration == "2_day":
            end = start + datetime.timedelta(days=2)
        elif plan_duration == "monthly":
            end = start + datetime.timedelta(days=30)
        elif plan_duration == "quarterly":
            end = start + datetime.timedelta(days=90)
        elif plan_duration == "yearly":
            end = start + datetime.timedelta(days=365)
        else:
            # Fallback to duration_months if plan_duration not recognized
            end = start + datetime.timedelta(days=30 * duration_months)

        return {
            "owner_id": owner_id,
            "gym_id": gym_id,
            "gym_name": gym_name,
            "user_name": user_name,
            "user_email": user_email,
            "plan_name": plan_name,
            "price": price,
            "plan_duration": plan_duration,
            "duration_months": duration_months,
            "start_date": start,
            "end_date": end,
            "status": "active",  # active, expired, cancelled
            **BaseSchema.timestamps()
        }


class MembershipRequestSchema(BaseSchema):

    @staticmethod
    def create_request(
        *,
        gym_id: str,
        gym_name: str,
        user_id: str = None,
        user_name: str = None,
        user_email: str = None,
        plan_name: str,
        price: float,
        message: str = None,
    ) -> Dict:
        return {
            "gym_id": gym_id,
            "gym_name": gym_name,
            "user_id": user_id,  # ObjectId of the user who sent the request
            "user_name": user_name,
            "user_email": user_email,
            "plan_name": plan_name,
            "price": price,
            "message": message,
            "status": "pending",  # pending, approved, rejected
            **BaseSchema.timestamps()
        }


class PaymentSchema(BaseSchema):

    @staticmethod
    def create_payment(
        *,
        owner_id: str,
        membership_id: str,
        gym_id: str,
        gym_name: str = "",
        member_name: str = "",
        plan_name: str = "",
        amount: float,
        payment_method: str = "cash",  # cash, upi, card, bank_transfer
        notes: str = None,
    ) -> Dict:
        return {
            "owner_id": owner_id,
            "membership_id": membership_id,
            "gym_id": gym_id,
            "gym_name": gym_name,
            "member_name": member_name,
            "plan_name": plan_name,
            "amount": amount,
            "payment_method": payment_method,
            "payment_date": timezone.now(),
            "status": "completed",  # completed, pending, failed
            "notes": notes,
            **BaseSchema.timestamps()
        }


class GymOwnerOTPSchema(BaseSchema):

    @staticmethod
    def create_otp(
        *,
        email: str,
        otp: str,
        purpose: str = "registration"  # registration, login, password_reset
    ) -> Dict:

        return {
            "email": email.lower(),
            "otp": otp,
            "purpose": purpose,
            "is_verified": False,
            "attempts": 0,
            "expires_at": timezone.now() + datetime.timedelta(minutes=10),
            **BaseSchema.timestamps()
        }
