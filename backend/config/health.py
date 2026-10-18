"""Cheap process liveness for hosting probes; external services may be asleep."""
from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def healthz(request):
    # Frequent platform probes must not wake Neon or consume its compute budget.
    # Deployment initialization checks the database before Gunicorn starts.
    response = JsonResponse({'status': 'ok'})
    response['Cache-Control'] = 'no-store'
    return response
