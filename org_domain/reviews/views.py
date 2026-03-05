from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from bson import ObjectId
from django.utils import timezone

from .mongo import org_gym_reviews
from .schema import ReviewSchema


def review_response(review_doc):
    """Format review document for API response"""
    return {
        "id": str(review_doc["_id"]),
        "gym_id": review_doc.get("gym_id"),
        "gym_name": review_doc.get("gym_name"),
        "user_name": review_doc.get("user_name"),
        "user_email": review_doc.get("user_email"),
        "rating": review_doc.get("rating"),
        "review_text": review_doc.get("review_text"),
        "helpful_count": review_doc.get("helpful_count", 0),
        "status": review_doc.get("status"),
        "created_at": review_doc.get("created_at").isoformat() if review_doc.get("created_at") else None,
        "updated_at": review_doc.get("updated_at").isoformat() if review_doc.get("updated_at") else None,
    }


@method_decorator(csrf_exempt, name="dispatch")
class CreateReviewView(APIView):
    """
    POST /api/org/reviews/create/
    Body: gym_id, gym_name, user_name, user_email, rating, review_text
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validate required fields
        if not data.get("gym_id") or not data.get("user_name") or not data.get("rating"):
            return Response(
                {"error": "gym_id, user_name, and rating are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate rating range
        try:
            rating = int(data.get("rating"))
            if rating < 1 or rating > 5:
                return Response(
                    {"error": "Rating must be between 1 and 5"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid rating value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create review document
        review_doc = ReviewSchema.create_gym_review(
            gym_id=data["gym_id"],
            gym_name=data.get("gym_name", ""),
            user_name=data["user_name"],
            user_email=data.get("user_email"),
            rating=rating,
            review_text=data.get("review_text"),
        )

        result = org_gym_reviews.insert_one(review_doc)

        created_review = org_gym_reviews.find_one({"_id": result.inserted_id})

        return Response(
            {"message": "Review created successfully", "review": review_response(created_review)},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GymReviewsListView(APIView):
    """
    GET /api/org/reviews/gym/<gym_id>/
    Returns all approved reviews for a specific gym
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, gym_id):
        reviews = org_gym_reviews.find({
            "gym_id": gym_id,
            "status": "approved"
        }).sort("created_at", -1)

        reviews_list = [review_response(r) for r in reviews]

        # Calculate rating statistics
        total_reviews = len(reviews_list)
        if total_reviews > 0:
            avg_rating = sum(r["rating"] for r in reviews_list) / total_reviews
            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for r in reviews_list:
                rating_counts[r["rating"]] += 1
        else:
            avg_rating = 0
            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        return Response({
            "reviews": reviews_list,
            "total_reviews": total_reviews,
            "average_rating": round(avg_rating, 1),
            "rating_counts": rating_counts,
        })


@method_decorator(csrf_exempt, name="dispatch")
class MarkReviewHelpfulView(APIView):
    """
    POST /api/org/reviews/<review_id>/helpful/
    Increment the helpful count for a review
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, review_id):
        try:
            result = org_gym_reviews.update_one(
                {"_id": ObjectId(review_id)},
                {"$inc": {"helpful_count": 1}}
            )

            if result.matched_count == 0:
                return Response(
                    {"error": "Review not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            updated_review = org_gym_reviews.find_one({"_id": ObjectId(review_id)})

            return Response(
                {"message": "Review marked as helpful", "review": review_response(updated_review)},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
