import os
import sys
import django
from django.template import Engine

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rakshak_project.settings')
django.setup()

engine = Engine.get_default()
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'))

success = True
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                engine.from_string(content)
                print(f"OK: {file}")
            except Exception as e:
                print(f"ERROR in {file}: {e}")
                success = False

if not success:
    sys.exit(1)
