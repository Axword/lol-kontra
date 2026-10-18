"""Exercise production asset collection and serving without a live database."""
from unittest.mock import patch

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import Client, override_settings


def test_collected_admin_assets_are_hashed_compressed_and_served(tmp_path):
    with override_settings(
        DEBUG=False,
        STATIC_ROOT=tmp_path,
        STATIC_URL='/static/',
        WHITENOISE_AUTOREFRESH=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {
                'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
            },
        },
    ):
        call_command('collectstatic', interactive=False, verbosity=0)
        asset_url = staticfiles_storage.url('admin/css/base.css')
        assert asset_url.startswith('/static/admin/css/base.')
        assert asset_url != '/static/admin/css/base.css'
        with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
                   side_effect=AssertionError('Static assets must not query the database')):
            response = Client().get(asset_url, secure=True, HTTP_ACCEPT_ENCODING='gzip')
        try:
            assert response.status_code == 200
            assert response['Content-Type'].startswith('text/css')
            assert response['Content-Encoding'] == 'gzip'
            assert 'immutable' in response['Cache-Control']
        finally:
            response.close()
