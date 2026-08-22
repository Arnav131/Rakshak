# backend/patrol/api_urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.api_start_patrol, name='api_start_patrol'),
    path('reports/', views.api_list_patrols, name='api_list_patrols'),
    path('<str:patrol_code>/', views.api_get_patrol_detail, name='api_patrol_detail'),
    path('<str:patrol_code>/submit/', views.api_submit_ratings, name='api_submit_ratings'),
    path('<str:patrol_code>/weights/', views.api_update_weights, name='api_update_weights'),
    path('<str:patrol_code>/decide/', views.api_submit_decision, name='api_submit_decision'),
]
