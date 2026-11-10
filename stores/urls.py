from django.urls import path

from . import views

urlpatterns = [
    path("stores", views.StoreCreateView.as_view()),
    path("stores/<int:pk>", views.StoreDetailView.as_view()),
]
