"""
seed_users.py
Creates demo accounts:
  controller / admin123  -> superuser (full access + /admin/)
  viewer     / viewer123  -> read-only viewer
"""
from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create controller (admin), viewer, and worker demo accounts.'

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

        # Worker account — in 'patrol_worker' group
        patrol_group, _ = Group.objects.get_or_create(name='patrol_worker')
        worker, _ = User.objects.get_or_create(username='worker')
        worker.is_staff = False
        worker.is_superuser = False
        worker.set_password('worker123')
        worker.first_name = 'Ramesh'
        worker.last_name = 'Kumar'
        worker.save()
        worker.groups.add(patrol_group)

        self.stdout.write(self.style.SUCCESS(
            'Created controller/admin123 (Controller), viewer/viewer123 (Viewer), '
            'and worker/worker123 (Patrol Worker).'
        ))