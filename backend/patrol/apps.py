# backend/patrol/apps.py
from django.apps import AppConfig


class PatrolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'patrol'
    verbose_name = 'Worker Patrol System'
