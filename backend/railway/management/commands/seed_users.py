"""
seed_users.py
Creates demo accounts:
  controller / admin123  -> superuser (full access + /admin/)
  viewer     / viewer123  -> read-only viewer
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create controller (admin) and viewer demo accounts.'

    def handle(self, *args, **options):
        controller, _ = User.objects.get_or_create(username='controller')
        controller.is_staff = True
        controller.is_superuser = True
        controller.set_password('admin123')
        controller.save()

        viewer, _ = User.objects.get_or_create(username='viewer')
        viewer.is_staff = False
        viewer.is_superuser = False
        viewer.set_password('viewer123')
        viewer.save()

        self.stdout.write(self.style.SUCCESS(
            'Created controller/admin123 (Controller) and viewer/viewer123 (Viewer).'
        ))