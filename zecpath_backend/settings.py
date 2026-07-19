import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# 1. DECOUPLED SECURITY CONFIGURATIONS
# ==========================================
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.onrender.com']

# ==========================================
# 2. APPLICATION DEFINITIONS
# ==========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-Party Packages
    'rest_framework',
    'rest_framework_simplejwt',
    'core',
    'django_filters',
    'storages',  # Added for Day 53 secure S3 connection storage layer
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'zecpath_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'zecpath_backend.wsgi.application'

# ==========================================
# 3. DATABASE ENGINE MAPPING
# ==========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ==========================================
# 4. IDENTITY & AUTHENTICATION SYSTEMS
# ==========================================
# Custom User Configuration (Day 8)
AUTH_USER_MODEL = 'core.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Django REST Framework Configuration (Day 9)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # 🚀 ACTIVATE THE CENTRALIZED EXCEPTION ENGINE HERE:
    'EXCEPTION_HANDLER': 'core.exceptions.custom_api_exception_handler',
    # 📉 Day 14: Production Pagination Layer
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,  # Limits maximum item count per network request to 10
}

# SimpleJWT Framework Configuration (Day 9)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUDIENCE': None,
    'ISSUER': None,
    'JSON_ENCODER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_FIELD': 'token_type',
}

# ==========================================
# 5. INTERNATIONALIZATION & ASSETS
# ==========================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Default fallback absolute filesystem paths for local development
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# 📧 Day 27: SaaS Communication Infrastructure Development Backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'ZecPath Careers <careers@zecpath.com>'


# ⚡ CELERY & REDIS DISTRIBUTED SYSTEM CONFIGURATIONS
# ⚡ WINDOWS EMULATION BREAKTHROUGH: Uses internal virtual memory instead of external servers
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Register Celery Beat scheduler database driver
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Add django_celery_beat to INSTALLED_APPS string array if not already present
INSTALLED_APPS += [
    'django_celery_beat',
]

# ==========================================
# 6. DAY 53: SECURE PRODUCTION CLOUD STORAGE (SUPABASE S3)
# ==========================================
# Checks if S3 Access Keys exist inside the host platform environment controls
USE_CLOUD_STORAGE = os.environ.get('AWS_ACCESS_KEY_ID') is not None

if USE_CLOUD_STORAGE:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.core.files.storage.StaticFilesStorage",
        },
    }
    
    # Read Keys from Render Environment Variables panel
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL')
    
    # Security Policy Configuration Tuning
    AWS_QUERYSTRING_AUTH = True            # Generates temporary cryptographically signed expiring links
    AWS_QUERYSTRING_EXPIRE = 900           # Link access authorization windows scale up to exactly 15 minutes
    AWS_DEFAULT_ACL = None                 # Enforces strict inheritance from private bucket configurations
    AWS_S3_FILE_OVERWRITE = False          # Appends hash tags to duplicate filenames to protect old user uploads