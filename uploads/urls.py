from django.urls import path

from . import views

urlpatterns = [
    path("uploads", views.UploadView.as_view()),
    path("images/<uuid:pk>.jpg", views.ImageView.as_view()),
]
