#!/bin/sh
set -eu
python manage.py bootstrap_database
python manage.py shell -c 'import os; from django.conf import settings; from django.contrib.sites.models import Site; Site.objects.update_or_create(pk=settings.SITE_ID,defaults={"domain":os.environ["PUBLIC_DOMAIN"],"name":"WORDS V"})'
python manage.py collectstatic --noinput
