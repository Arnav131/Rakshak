# backend/rakshak_project/urls.py
"""
Root URL configuration for the Rakshak project.

Routes:
  /            → Dashboard (sensors app)
  /alerts/     → Alerts page
  /tickets/    → Maintenance Tickets page
  /map/        → Railway Map page
  /simulation/ → Live Simulation page (admin/staff only — enforced in view + nav)
  /api/        → JSON API endpoints (map data)
  /api/ai/     → AI prediction endpoints (ai_integration)
  /api/predict/ → Prediction endpoints (sensors app)
  /api/simulation/ → Simulation run endpoint (admin/staff only)
"""
from django.contrib import admin
from django.urls import path, include
from core.views import custom_logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/logout/', custom_logout_view, name='logout'),
    path('logout/', custom_logout_view, name='direct_logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('sensors.urls')),
    path('alerts/', include('alerts.urls')),
    path('tickets/', include('tickets.urls')),
    path('map/', include('map_view.urls')),
    path('readiness/', include('readiness.urls')),
    path('simulation/', include('simulation.urls')),
    path('patrol/', include('patrol.urls')),
    path('api/', include('map_view.api_urls')),
    path('api/predict/', include('sensors.api_urls')),
    path('api/ai/', include('ai_integration.api_urls')),
    path('api/simulation/', include('simulation.api_urls')),
    path('api/patrol/', include('patrol.api_urls')),
]
