from django.urls import path
from .views import (
    CreatePaymentView,
    ListPaymentsView,
    GetPaymentView,
    UpdatePaymentView,
    DeletePaymentView,
)
from .trial_views import CreateTrialPaymentView

urlpatterns = [
    path("create/", CreatePaymentView.as_view(), name="create-payment"),
    path("trial/", CreateTrialPaymentView.as_view(), name="create-trial-payment"),
    path("list/", ListPaymentsView.as_view(), name="list-payments"),
    path("<str:payment_id>/", GetPaymentView.as_view(), name="get-payment"),
    path("update/<str:payment_id>/", UpdatePaymentView.as_view(), name="update-payment"),
    path("delete/<str:payment_id>/", DeletePaymentView.as_view(), name="delete-payment"),
]
