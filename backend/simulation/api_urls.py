# backend/simulation/api_urls.py
from django.urls import path

from . import views

app_name = "simulation_api"

urlpatterns = [
    path("run/", views.api_run_simulation, name="run"),
]
