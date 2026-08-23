# backend/rakshak_project/settings.py
"""
Django settings for the Rakshak project — Phase 1 Prototype.

This configuration uses:
  - Supabase/PostgreSQL as the only supported database backend
  - DATABASE_URL as the single database configuration input
  - Templates from frontend/templates/
  - Static files from frontend/static/
  - Authentication middleware and staff-only controls for privileged views
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


# Build paths relative to the backend/ directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from project root or backend directory
load_dotenv(BASE_DIR.parent / '.env')
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'rakshak-phase1-prototype-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    f"https://{RENDER_EXTERNAL_HOSTNAME}"
] if RENDER_EXTERNAL_HOSTNAME else []

extra_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS')
if extra_csrf_origins:
    CSRF_TRUSTED_ORIGINS += extra_csrf_origins.split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Rakshak apps
    'core',
    'sensors',
    'alerts',
    'tickets',
    'map_view',
    'railway',
    'ai_integration',
    'simulation',
    'readiness',
    'patrol',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'railway.middleware.CurrentUserMiddleware',
]

ROOT_URLCONF = 'rakshak_project.urls'

# ---------------------------------------------------------------------------
# Templates — served from frontend/templates/
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR.parent / 'frontend' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.navigation',
                'core.context_processors.project_meta',
            ],
        },
    },
]

WSGI_APPLICATION = 'rakshak_project.wsgi.application'

# ---------------------------------------------------------------------------
# Database - Supabase/PostgreSQL with dev fallback
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=int(os.environ.get('DATABASE_CONN_MAX_AGE', '0')),
            ssl_require=True if 'supabase' in DATABASE_URL or 'sslmode=require' in DATABASE_URL else False,
        )
    }
elif all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'CONN_MAX_AGE': int(os.environ.get('DATABASE_CONN_MAX_AGE', '0')),
            'OPTIONS': {
                'sslmode': 'require',
            }
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Static files — served from frontend/static/
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR.parent / 'frontend' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# AI Integration — Provider Configuration
# ---------------------------------------------------------------------------
# This is the SINGLE configuration point for all AI providers.
#
# To switch AI backends, change DEFAULT_PROVIDER.
# To add a new provider, add an entry to PROVIDERS.
# Business logic is completely unaffected by these changes.
#
# FUTURE PROVIDERS:
#   'cloud': CloudAIProvider  — calls a remote AI API
#   'llm':   LLMProvider      — sends data to an LLM for analysis
#   'ensemble': EnsembleProvider — combines multiple providers
#
# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This configuration block does NOT affect the database.
# Current DB: PostgreSQL
# Future DB: PostgreSQL
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
SENSOR_SOURCE_CLASS = 'ai_integration.sensor_source.MockSensorSource'

RAKSHAK_AI = {
    # Which provider to use by default.
    # Change this single value to switch the entire AI backend.
    'DEFAULT_PROVIDER': 'local',

    'PROVIDERS': {
        # --- Local Pickle/PyTorch Provider ---
        # Loads trained models from ai_engin/trained_models/
        # This is the default for prototype and local development.
        'local': {
            'CLASS': 'ai_integration.local_provider.LocalPickleProvider',
            'MODEL_DIR': str(BASE_DIR / 'ai_models'),
            'WINDOW_SIZE': 16,
            'ALERT_THRESHOLD': 0.7,
            'CRITICAL_THRESHOLD': 0.9,
        },

        # --- Future: Cloud AI Provider ---
        # Uncomment and configure when moving to cloud inference.
        # 'cloud': {
        #     'CLASS': 'ai_integration.cloud_provider.CloudAIProvider',
        #     'API_URL': 'https://your-cloud-endpoint.com/predict',
        #     'API_KEY_ENV': 'RAKSHAK_CLOUD_API_KEY',
        #     'TIMEOUT_SECONDS': 10,
        # },

        # --- Future: LLM Provider ---
        # Uncomment and configure when integrating with an LLM.
        # 'llm': {
        #     'CLASS': 'ai_integration.llm_provider.LLMProvider',
        #     'MODEL_NAME': 'gpt-4',
        #     'API_KEY_ENV': 'RAKSHAK_LLM_API_KEY',
        # },
    },
}
# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'
