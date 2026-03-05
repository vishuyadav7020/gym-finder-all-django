from django.urls import path
from .views import CreateReviewView, GymReviewsListView, MarkReviewHelpfulView

urlpatterns = [
    path("create/", CreateReviewView.as_view(), name="create_review"),
    path("gym/<str:gym_id>/", GymReviewsListView.as_view(), name="gym_reviews"),
    path("<str:review_id>/helpful/", MarkReviewHelpfulView.as_view(), name="mark_helpful"),
]
