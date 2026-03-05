import datetime
from django.utils import timezone
from typing import Dict


class ReviewSchema:
    
    @staticmethod
    def create_gym_review(
        *,
        gym_id: str,
        gym_name: str,
        user_name: str,
        user_email: str = None,
        rating: int,  # 1-5
        review_text: str = None,
    ) -> Dict:
        
        return {
            "gym_id": gym_id,
            "gym_name": gym_name,
            "user_name": user_name,
            "user_email": user_email,
            "rating": rating,
            "review_text": review_text,
            "helpful_count": 0,
            "status": "approved",  # approved, pending, rejected
            "created_at": timezone.now(),
            "updated_at": timezone.now()
        }
