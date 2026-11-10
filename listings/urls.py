from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/listings", views.StoreListingView.as_view()),
    path("listings/<int:pk>", views.ListingDetailView.as_view()),
    path("listings/<int:pk>/status", views.ListingStatusView.as_view()),
]
