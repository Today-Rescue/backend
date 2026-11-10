from django.urls import path

from . import views

urlpatterns = [
    path("geo/region", views.RegionView.as_view()),
    path("geo/search", views.SearchView.as_view()),
]
