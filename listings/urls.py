from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/campaigns", views.StoreCampaignView.as_view()),
    path("stores/<int:store_id>/campaigns/discount", views.StoreDiscountView.as_view()),
    path("campaigns/<int:pk>", views.CampaignDetailView.as_view()),
    path("campaigns/<int:pk>/status", views.CampaignStatusView.as_view()),
]
