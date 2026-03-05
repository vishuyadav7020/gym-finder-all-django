from django.urls import path
from .views import (
    CreateMemberView,
    ListMembersView,
    UpdateMemberView,
    DeleteMemberView,
    RenewMemberView,
    CreateMembershipRequestView,
    ListMembershipRequestsView,
    ListUserMembershipRequestsView,
    UpdateMembershipRequestView,
)
from .user_views import GetUserMembershipsView

urlpatterns = [
    # Member CRUD
    path("create/", CreateMemberView.as_view(), name="create-member"),
    path("list/", ListMembersView.as_view(), name="list-members"),
    path("user/<str:user_id>/", GetUserMembershipsView.as_view(), name="get-user-memberships"),
    path("update/<str:member_id>/", UpdateMemberView.as_view(), name="update-member"),
    path("delete/<str:member_id>/", DeleteMemberView.as_view(), name="delete-member"),
    path("renew/<str:member_id>/", RenewMemberView.as_view(), name="renew-member"),

    # Membership Requests
    path("request/create/", CreateMembershipRequestView.as_view(), name="request-create"),
    path("request/list/", ListMembershipRequestsView.as_view(), name="request-list"),
    path("request/user/<str:user_id>/", ListUserMembershipRequestsView.as_view(), name="request-list-by-user"),
    path("request/update/<str:request_id>/", UpdateMembershipRequestView.as_view(), name="request-update"),
]
