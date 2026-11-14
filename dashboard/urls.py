from django.urls import path

from . import recommend, views

urlpatterns = [
    path("stores/<int:store_id>/dashboard", views.DashboardView.as_view()),
    path("stores/<int:store_id>/recommendations", recommend.RecommendationView.as_view()),
]
