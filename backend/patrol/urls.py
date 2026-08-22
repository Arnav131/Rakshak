# backend/patrol/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.patrol_page, name='patrol_page'),
    path('admin/', views.patrol_admin_page, name='patrol_admin_page'),
]
