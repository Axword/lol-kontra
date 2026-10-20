"""Staff-only board editor using the same facts and checks as the game."""
import hashlib
import json
from datetime import date, timedelta
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.players.models import Player
from .generator import (CONDITION_POOL, MEDIUM, MIN_CANDIDATES, ROLE_ORDER,
                        build_condition_pool, count_candidates, validate_daily, validate_slots)
from .models import Daily, DailySlot, DailySlotCondition


def condition_key(condition):
    payload = json.dumps(condition[2:5], sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def condition_catalog(daily=None):
    players = list(Player.objects.order_by('slug'))
    conditions = build_condition_pool(players, minimum=1)
    known_countries = {c[4] for c in conditions if c[2] == 'country' and c[3] == 'eq'}
    conditions.extend(('origin', MEDIUM, 'country', 'eq', country, f'Narodowość: {country}', f'Nationality: {country}')
                      for country in sorted({p.country_code for p in players} - known_countries) if country)
    for year in range(2012, timezone.localdate().year + 1):
        conditions.extend([
            ('worlds_era', MEDIUM, 'worlds_appearance', 'eq', year,
             f'Zagrał na Worlds {year}', f'Played at Worlds {year}'),
            ('worlds_era', MEDIUM, 'worlds_last_year', 'lt', year,
             f'Ostatni udział w Worlds przed {year}', f'Last Worlds appearance before {year}'),
            ('worlds_debut', MEDIUM, 'worlds_debut_year', 'lt', year,
             f'Debiutował na Worlds przed {year}', f'Worlds debut before {year}'),
        ])
        if year <= 2023:
            conditions.append(('elimination_stage', MEDIUM, 'worlds_group_exit_before', 'eq', year,
                f'Choć raz odpadł w grupie Worlds przed {year} (główny turniej)',
                f'Eliminated in Worlds main-event groups at least once before {year}'))
    conditions.extend([
        ('origin', MEDIUM, 'country_excluded', 'eq', 'KR', 'Nie jest Koreańczykiem', 'Not Korean'),
        ('playin', MEDIUM, 'worlds_playin_appearance', 'eq', True, 'Zagrał w play-in Worlds', 'Played in Worlds play-in'),
        ('league', MEDIUM, 'career_regions_min', 'gte', 2, 'Grał w ligach co najmniej 2 różnych regionów', 'Played in domestic leagues in at least 2 regions'),
    ])
    # Keep existing, reviewed custom clues selectable when reopening their board.
    themes = {c[2]: c[0] for c in CONDITION_POOL}
    if daily:
        conditions.extend((themes.get(c.condition_type, c.condition_type), MEDIUM,
                           c.condition_type, c.operator, c.value, c.label_pl, c.label_en)
                          for c in DailySlotCondition.objects.filter(slot__daily=daily))
    return dict(sorted({condition_key(c): c for c in conditions}.items(), key=lambda row: row[1][5].casefold()))


def can_edit(user):
    return user.is_active and user.is_staff and all(user.has_perm(f'dailies.{action}_{model}')
        for action in ('add', 'change') for model in ('daily', 'dailyslot', 'dailyslotcondition'))


def virtual_slots(selections, catalog):
    if not isinstance(selections, dict) or set(selections) != set(ROLE_ORDER):
        raise ValueError('Wybierz warunki dla pięciu pozycji.')
    slots = []
    for role in ROLE_ORDER:
        keys = selections[role]
        if not isinstance(keys, list) or not 1 <= len(keys) <= 2 or any(not isinstance(k, str) or k not in catalog for k in keys):
            raise ValueError(f'{role.upper()}: wybierz jeden lub dwa warunki z listy.')
        conditions = [SimpleNamespace(condition_type=catalog[k][2], operator=catalog[k][3], value=catalog[k][4]) for k in keys]
        slots.append(SimpleNamespace(role=role, conditions=SimpleNamespace(all=lambda conditions=conditions: conditions)))
    return slots


@never_cache
def builder_view(request, model_admin):
    if not can_edit(request.user):
        raise PermissionDenied
    if request.method == 'GET':
        daily = get_object_or_404(Daily, pk=request.GET['daily']) if request.GET.get('daily') else None
        catalog = condition_catalog(daily)
        initial = {
            'date': str(daily.date if daily else timezone.localdate() + timedelta(days=1)),
            'author_name': daily.author_name if daily else '',
            'author_url': daily.author_url if daily else '',
            'author_description': daily.author_description if daily else '',
            'selections': {role: [] for role in ROLE_ORDER},
        }
        if daily:
            for slot in daily.slots.prefetch_related('conditions'):
                initial['selections'][slot.role] = [condition_key((None, None, c.condition_type, c.operator, c.value)) for c in slot.conditions.all()]
        locked = bool(daily and (daily.date < timezone.localdate() or daily.submissions.exists()))
        return render(request, 'admin/dailies/builder.html', {
            **model_admin.admin_site.each_context(request), 'title': 'Edytor reguł',
            'opts': Daily._meta, 'initial': initial, 'locked': locked,
            'conditions': [{'id': key, 'label': c[5]} for key, c in catalog.items()],
            'roles': [('top', 'TOP'), ('jungle', 'JUNGLE'), ('mid', 'MID'), ('adc', 'ADC'), ('support', 'SUPPORT')],
        })
    if request.method != 'POST':
        return JsonResponse({'error': 'Użyj formularza edytora.'}, status=405)
    try:
        if len(request.body) > 16384:
            raise ValueError('Formularz jest za duży.')
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError('Nieprawidłowy formularz.')
        target = date.fromisoformat(data.get('date', ''))
        action = data.get('action', 'preview')
        if action not in ('preview', 'draft', 'publish'):
            raise ValueError('Nieprawidłowa akcja.')
        author = {key: str(data.get(key, '')).strip() for key in ('author_name', 'author_url', 'author_description')}
        if len(author['author_name']) > 64 or len(author['author_url']) > 200 or len(author['author_description']) > 180:
            raise ValueError('Dane autora są za długie.')
        if author['author_url']:
            from django.core.validators import URLValidator
            from django.core.exceptions import ValidationError
            try:
                URLValidator(schemes=['http', 'https'])(author['author_url'])
            except ValidationError as exc:
                raise ValueError('Podaj poprawny adres strony autora.') from exc
        existing = Daily.objects.filter(date=target).first()
        catalog = condition_catalog(existing)
        slots = virtual_slots(data.get('selections'), catalog)
        pools = [count_candidates(slot) for slot in slots]
        summary = {slot.role: {'count': len(pool), 'players': [p.nickname for p in pool]}
                   for slot, pool in zip(slots, pools)}
        issues = []
        try:
            validate_slots(slots, MIN_CANDIDATES, bool(author['author_name']))
        except ValueError as exc:
            issues.append(str(exc))
        if action == 'preview':
            return JsonResponse({'slots': summary, 'issues': issues, 'valid': not issues})
        if issues:
            return JsonResponse({'slots': summary, 'issues': issues, 'error': 'Popraw warunki przed zapisaniem planszy.'}, status=400)
        if target < timezone.localdate():
            raise ValueError('Nie można zmieniać archiwalnych plansz.')
        with transaction.atomic():
            daily, _ = Daily.objects.select_for_update().get_or_create(date=target)
            if daily.submissions.exists():
                raise ValueError('Na tej planszy rozpoczęto już grę. Wybierz inny dzień.')
            daily.author_name, daily.author_url, daily.author_description = author.values()
            daily.minimum_candidates = MIN_CANDIDATES
            daily.status = 'published' if action == 'publish' else 'draft'
            daily.published_at = timezone.now() if action == 'publish' else None
            daily.created_by = request.user
            daily.save()
            for position, slot in enumerate(slots, 1):
                saved, _ = DailySlot.objects.get_or_create(daily=daily, role=slot.role, defaults={'position': position})
                saved.conditions.all().delete()
                for order, key in enumerate(data['selections'][slot.role]):
                    c = catalog[key]
                    DailySlotCondition.objects.create(slot=saved, condition_type=c[2], operator=c[3], value=c[4],
                                                      label_pl=c[5], label_en=c[6], order=order)
            validate_daily(daily)
            model_admin.log_change(request, daily, f'Edytor reguł: {action}')
        return JsonResponse({'slots': summary, 'issues': [], 'saved': True, 'published': action == 'publish',
                             'url': reverse('admin:dailies_daily_builder') + f'?daily={daily.pk}'})
    except (ValueError, TypeError, KeyError, IntegrityError) as exc:
        message = 'Ten termin został właśnie zajęty. Odśwież edytor.' if isinstance(exc, IntegrityError) else str(exc)
        return JsonResponse({'error': message}, status=400)
