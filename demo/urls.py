from django.urls import path

from . import views

urlpatterns = [
    path("demo/reset", views.DemoResetView.as_view()),
]
