from django.urls import path
from .views import (
    CreateGymView,
    ListGymsView,
    GetGymView,
    UpdateGymView,
    DeleteGymView,
    PublicListGymsView,
    PublicGymDetailView,
)

urlpatterns = [
    path("create/", CreateGymView.as_view(), name="gym-create"),
    path("list/", ListGymsView.as_view(), name="gym-list"),
    path("public/list/", PublicListGymsView.as_view(), name="gym-public-list"),
    path("public/<str:gym_id>/", PublicGymDetailView.as_view(), name="gym-public-detail"),
    path("update/<str:gym_id>/", UpdateGymView.as_view(), name="gym-update"),
    path("delete/<str:gym_id>/", DeleteGymView.as_view(), name="gym-delete"),
    path("<str:gym_id>/", GetGymView.as_view(), name="gym-detail"),
]
