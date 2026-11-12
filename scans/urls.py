from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/scans", views.ScanCreateView.as_view()),
    path("scans/<int:pk>", views.ScanDetailView.as_view()),
    path("scans/<int:pk>/confirm", views.ScanConfirmView.as_view()),
]
