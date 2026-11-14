from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/campaigns", views.StoreCampaignView.as_view()),
    path("stores/<int:store_id>/campaigns/discount", views.StoreDiscountView.as_view()),
    path("stores/<int:store_id>/campaigns/bundle", views.StoreBundleView.as_view()),
    path("stores/<int:store_id>/campaigns/live", views.StoreLiveView.as_view()),
    path("stores/<int:store_id>/actions", views.StoreActionsView.as_view()),
    path("stores/<int:store_id>/bundles/recommend", views.BundleRecommendView.as_view()),
    path("stores/<int:store_id>/bundles/calculate", views.BundleCalculateView.as_view()),
    path("campaigns/<int:pk>", views.CampaignDetailView.as_view()),
    path("campaigns/<int:pk>/status", views.CampaignStatusView.as_view()),
    path("campaigns/<int:pk>/sales", views.CampaignSalesView.as_view()),
]
