import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')

# CSRF trusted origins for production
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else []

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

    # local
    'apps.players',
    'apps.dailies',
    'apps.submissions',
    'apps.scoring',
    'apps.users',
    'apps.admin_tools',
]

# Conditionally add celery apps only if not on Render (no Redis available on free tier)
if not os.getenv('RENDER'):
    INSTALLED_APPS += ['django_celery_beat', 'django_celery_results']

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # for static files on Render
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

# Database – Neon.tech PostgreSQL (free tier) or local Docker Postgres
# DATABASE_URL takes priority (Neon provides this format)
import dj_database_url

DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require='neon.tech' in DATABASE_URL or os.getenv('DB_SSL_REQUIRE', 'false').lower() == 'true',
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'lolroster'),
            'USER': os.getenv('POSTGRES_USER', 'lolroster'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'lolroster'),
            'HOST': os.getenv('POSTGRES_HOST', 'db'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

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
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise for static files
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

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

# CORS – allow Vercel frontend and local dev
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True
# Also allow all origins in dev
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'LoL Roster Challenge API',
    'DESCRIPTION': 'Worlds XI Daily Challenge',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Celery – optional, only when Redis is available
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

# Redis cache – fallback to local memory when Redis is unavailable
REDIS_URL = os.getenv('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
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

# Logging – structlog (simplified for Render)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
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
