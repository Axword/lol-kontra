import os
import ipaddress
import re
import structlog
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    if value not in ('true', 'false', '1', '0'):
        raise ImproperlyConfigured(f'{name} must be true or false')
    return value in ('true', '1')


def env_list(name, default=''):
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]


def valid_host(host):
    if host.startswith('[') or host.endswith(']'):
        if not (host.startswith('[') and host.endswith(']')):
            return False
        try:
            return ipaddress.ip_address(host[1:-1]).version == 6
        except ValueError:
            return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(len(host) <= 253 and all(
            re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label, re.I)
            for label in host.rstrip('.').split('.')
        ))


def origin_list(name, default=''):
    origins = env_list(name, default)
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            allowed_schemes = ('http', 'https') if DEBUG else ('https',)
            valid = (
                parsed.scheme in allowed_schemes and parsed.hostname
                and valid_host(parsed.hostname) and '*' not in origin
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment
                and (parsed.port is None or 0 < parsed.port <= 65535)
                and not any(character.isspace() for character in origin)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ImproperlyConfigured(f'{name} must contain explicit origins with no path; production requires HTTPS')
    return origins


DEBUG = env_bool('DJANGO_DEBUG', True)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-change-me' if DEBUG else '')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]' if DEBUG else '')
if not DEBUG:
    if (
        len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5
        or SECRET_KEY.lower().startswith(('django-insecure-', 'dev-secret', 'change-me', 'changeme'))
    ):
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a unique production secret of at least 50 characters')
    if not ALLOWED_HOSTS or any(not valid_host(host) or '*' in host for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain explicit hostnames or IP addresses without wildcards or ports')

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Enable only behind a proxy which overwrites this header and blocks direct access.
SECURE_PROXY_SSL_HEADER = (
    ('HTTP_X_FORWARDED_PROTO', 'https') if env_bool('DJANGO_TRUST_PROXY_HEADERS') else None
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.postgres',

    # 3rd party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.discord',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'django_celery_beat',
    'django_celery_results',

    # local
    'apps.players',
    'apps.dailies',
    'apps.submissions',
    'apps.scoring',
    'apps.users',
    'apps.admin_tools',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'lolroster' if DEBUG else ''),
        'USER': os.getenv('POSTGRES_USER', 'lolroster' if DEBUG else ''),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'lolroster' if DEBUG else ''),
        'HOST': os.getenv('POSTGRES_HOST', 'db' if DEBUG else ''),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# Application credentials can be separate from the owner's deployment URL.
database_url_name = 'DATABASE_RUNTIME_URL' if os.getenv('DATABASE_RUNTIME_URL') else 'DATABASE_URL'
if os.getenv(database_url_name):
    from .database import postgres_config
    try:
        DATABASES['default'] = postgres_config(os.environ[database_url_name])
    except ValueError:
        raise ImproperlyConfigured(f'{database_url_name} must be a valid PostgreSQL connection URL') from None

if not DEBUG:
    database = DATABASES['default']
    if any(not database[name] for name in ('NAME', 'USER', 'PASSWORD', 'HOST')):
        raise ImproperlyConfigured('Production database requires explicit POSTGRES_DB/USER/PASSWORD/HOST or DATABASE_URL credentials')
    if len(database['PASSWORD']) < 16 or database['PASSWORD'].lower() in ('lolroster', 'postgres', 'password', 'change-me', 'changeme'):
        raise ImproperlyConfigured('Production database password must be non-default and at least 16 characters')

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pl'
TIME_ZONE = os.getenv('DAILY_TIMEZONE', 'Europe/Warsaw')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_ID = 1

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 30,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '120/min',
        'submission': '5/min',
    }
}

# CORS
CORS_ALLOWED_ORIGINS = origin_list('CORS_ALLOWED_ORIGINS', 'http://localhost:3000' if DEBUG else '')
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = origin_list('CSRF_TRUSTED_ORIGINS')

# drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'LoL Roster Challenge API',
    'DESCRIPTION': 'Worlds XI Daily Challenge',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/2')
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Allauth
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_REQUIRED = False

# Redis cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://redis:6379/0'),
    }
}

# Scoring config – can be overridden in DB
SCORING = {
    'COMMON': int(os.getenv('SCORING_COMMON', 10)),
    'RARE': int(os.getenv('SCORING_RARE', 25)),
    'EPIC': int(os.getenv('SCORING_EPIC', 60)),
    'LEGENDARY': int(os.getenv('SCORING_LEGENDARY', 120)),
    'DIAMOND_BONUS': int(os.getenv('SCORING_DIAMOND_BONUS', 50)),
    'THRESHOLD_RARE': 20.0,
    'THRESHOLD_EPIC': 10.0,
    'THRESHOLD_LEGENDARY': 1.0,
}

# Logging – structlog
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'structlog.stdlib.ProcessorFormatter',
            'processor': structlog.processors.JSONRenderer(),
        },
        'console': {
            '()': 'structlog.stdlib.ProcessorFormatter',
            'processor': structlog.dev.ConsoleRenderer(),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Sentry
if os.getenv('SENTRY_DSN'):
    import sentry_sdk
    sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'), traces_sample_rate=0.1)
