# backend/tickets/urls.py
"""URL routes for the tickets app."""

from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.tickets_page, name='tickets'),
    path('api/search/', views.tickets_search, name='tickets_search'),
]
