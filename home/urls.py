from django.urls import path

from . import views

urlpatterns = [
    path("stores/<int:store_id>/home", views.HomeView.as_view()),
]
