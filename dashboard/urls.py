from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/dashboard", views.DashboardView.as_view()),
]
