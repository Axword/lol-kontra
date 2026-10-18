"""Hosting probes must remain independent of PostgreSQL, Redis and DRF."""
from unittest.mock import patch

import pytest
from django.test import Client, override_settings


@pytest.mark.parametrize('method', ['get', 'head'])
def test_liveness_does_not_access_database_cache_or_api_throttle(method, tmp_path):
    with (
        override_settings(STATIC_ROOT=tmp_path),
        patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
              side_effect=AssertionError('Liveness must not connect to a database')),
        patch('django.core.cache.backends.redis.RedisCache.get',
              side_effect=AssertionError('Liveness must not read Redis')),
        patch('django.core.cache.backends.redis.RedisCache.set',
              side_effect=AssertionError('Liveness must not write Redis')),
        patch('rest_framework.throttling.SimpleRateThrottle.allow_request',
              side_effect=AssertionError('Liveness must not use API throttling')),
    ):
        response = getattr(Client(), method)('/healthz/', secure=True)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/json'
    assert response['Cache-Control'] == 'no-store'
    if method == 'get':
        # No versions, deployment configuration or game data are disclosed.
        assert response.json() == {'status': 'ok'}
    else:
        assert response.content == b''


def test_liveness_rejects_mutating_requests(tmp_path):
    with override_settings(STATIC_ROOT=tmp_path):
        response = Client().post('/healthz/', secure=True)
    assert response.status_code == 405
