# backend/readiness/urls.py
from django.urls import path
from . import views

app_name = "readiness"

urlpatterns = [
    path("", views.readiness_page, name="readiness_page"),
    path("api/cases/", views.api_get_cases, name="api_cases"),
    path("api/cases/<str:case_code>/", views.api_get_case_detail, name="api_case_detail"),
    path("api/cases/<str:case_code>/sign-off/", views.api_sign_off_item, name="api_sign_off"),
    path("api/cases/<str:case_code>/decide/", views.api_submit_decision, name="api_decide"),
]
