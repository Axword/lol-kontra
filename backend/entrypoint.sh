#!/bin/sh
set -eu

# Versioned migrations install the offline release. Failures stop startup.
# The PostgreSQL advisory lock serializes concurrent container initialization.
python manage.py bootstrap_database
python manage.py collectstatic --noinput

exec "$@"
