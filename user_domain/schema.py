from datetime import datetime
from bson import ObjectId


class UserSchema:
    """Schema for regular user (member) documents in MongoDB"""

    @staticmethod
    def create_user(full_name, email, password_hash, role="member", phone_number=None):
        """
        Create a new user document
        
        Args:
            full_name: User's full name
            email: User's email address
            password_hash: Hashed password
            role: User role (default: "member")
            phone_number: Optional phone number
            
        Returns:
            dict: User document ready for MongoDB insertion
        """
        return {
            "full_name": full_name,
            "email": email.lower(),
            "password": password_hash,
            "role": role,
            "phone_number": phone_number,
            "is_verified": False,
            "is_active": True,
            "profile_image": None,
            "date_of_birth": None,
            "gender": None,
            "address": None,
            "city": None,
            "state": None,
            "pincode": None,
            "emergency_contact": None,
            "fitness_goals": [],
            "preferred_workout_time": None,
            "gym_memberships": [],  # Array of gym IDs user is member of
            "favorite_gyms": [],  # Array of gym IDs user has favorited
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": None,
        }

    @staticmethod
    def update_user(updates):
        """
        Prepare user update document
        
        Args:
            updates: Dictionary of fields to update
            
        Returns:
            dict: Update document with timestamp
        """
        updates["updated_at"] = datetime.utcnow()
        return updates


class UserOTPSchema:
    """Schema for user OTP verification documents"""

    @staticmethod
    def create_otp(user_id, email, otp_code, expiry_time):
        """
        Create OTP document for email verification
        
        Args:
            user_id: User's ObjectId
            email: User's email address
            otp_code: Generated OTP code
            expiry_time: OTP expiration datetime
            
        Returns:
            dict: OTP document ready for MongoDB insertion
        """
        return {
            "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
            "email": email.lower(),
            "otp": otp_code,
            "expiry": expiry_time,
            "is_used": False,
            "created_at": datetime.utcnow(),
        }
