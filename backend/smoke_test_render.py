import sys
import os
#Je;;p


# add backend dir to path
sys.path.append(r'c:\Users\devil\Downloads\PROTOTYPE_1.0\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rakshak_project.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user, created = User.objects.get_or_create(username='testuser')
if created:
    user.set_password('testpass123')
    user.save()

client = Client()
client.force_login(user)

try:
    response = client.get('/')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Dashboard rendered successfully without NoReverseMatch!")
    else:
        print("Error rendering dashboard. See status code.")
except Exception as e:
    print(f"Exception occurred: {e}")
