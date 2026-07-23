import os

# Only initialize Celery when Redis is available (not on Render free tier)
if os.getenv('CELERY_BROKER_URL') or os.getenv('REDIS_URL'):
    try:
        from .celery import app as celery_app
        __all__ = ('celery_app',)
    except ImportError:
        __all__ = ()
else:
    __all__ = ()
