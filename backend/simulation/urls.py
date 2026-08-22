# backend/simulation/urls.py
from django.urls import path

from . import views

app_name = "simulation"

urlpatterns = [
    path("", views.simulation_page, name="page"),
]
