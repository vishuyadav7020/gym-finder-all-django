from django.urls import path
from .views import (
    UserRegisterView,
    UserLoginView,
    VerifyOTPView,
    ResendOTPView,
)
from .profile_views import UserProfileView
from .favorite_views import ToggleFavoriteGymView, GetFavoriteGymsView, CheckFavoriteStatusView

urlpatterns = [
    path("register/", UserRegisterView.as_view(), name="user-register"),
    path("login/", UserLoginView.as_view(), name="user-login"),
    path("verify-otp/", VerifyOTPView.as_view(), name="user-verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="user-resend-otp"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("favorite/toggle/", ToggleFavoriteGymView.as_view(), name="toggle-favorite"),
    path("favorite/list/", GetFavoriteGymsView.as_view(), name="list-favorites"),
    path("favorite/check/<str:gym_id>/", CheckFavoriteStatusView.as_view(), name="check-favorite"),
]
