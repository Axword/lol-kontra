"""Publish the reviewed November 4 opponent board without rewriting any game."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from django.db import migrations, models, transaction
from django.utils import timezone

RELEASE_FILE = 'worlds_opponent_board_2026_11_04_v1.json'
RELEASE_SHA256 = '8449e30fa7438d4567b8d5e21a2548c3b10af83b1a8a0736405dba239351daa9'
DAY = date(2026, 11, 4)
ROLES = ['top', 'jungle', 'mid', 'adc', 'support']


def load_release():
    raw = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError('November 4 opponent board checksum mismatch')
    source = json.loads(raw)
    if (source['schema_version'] != 1 or source['release'] != 'worlds-opponent-board-2026-11-04-v1'
            or source['date'] != DAY.isoformat()
            or [slot['role'] for slot in source['slots']] != ROLES
            or sorted(len(slot['conditions']) for slot in source['slots']) != [1, 1, 2, 2, 2]):
        raise ValueError('Unexpected November 4 opponent board release')
    for slot in source['slots']:
        candidates = slot['audited_candidates']
        if candidates != sorted(set(candidates)) or not 18 <= len(candidates) <= 150:
            raise ValueError('Opponent board requires broad verified answer pools')
    return source


def install(apps, schema_editor):
    source = load_release()
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Player = apps.get_model('players', 'Player')
    if not Player.objects.using(alias).exists():
        return
    required = {slug for slot in source['slots'] for slug in slot['audited_candidates']}
    present = set(Player.objects.using(alias).filter(slug__in=required).values_list('slug', flat=True))
    if present != required:
        raise ValueError('November 4 opponent board candidate identities are missing')
    opponent_candidates = source['slots'][2]['audited_candidates']
    for attrs in Player.objects.using(alias).filter(slug__in=opponent_candidates).values_list('attributes', flat=True):
        evidence = (attrs or {}).get('worlds_opponents') or {}
        if (evidence.get('complete') is not True or evidence.get('scope') != 'worlds_before_2026'
                or evidence.get('complete_through_year') != source['opponents_through_year']
                or evidence.get('source_sha256') != source['source_snapshot_sha256']
                or 'geng' not in evidence.get('teams', [])):
            raise ValueError('Verified Gen.G opponent evidence must be installed before this board')
    with transaction.atomic(using=alias):
        boards = list(Daily.objects.using(alias).select_for_update().filter(date=DAY).order_by('pk'))
        target = next((board for board in boards if board.locale_seed == source['release']), None)
        if target and target.is_current:
            return
        Daily.objects.using(alias).filter(date=DAY, is_current=True).update(is_current=False)
        if target:
            Daily.objects.using(alias).filter(pk=target.pk).update(is_current=True)
            return
        # Existing slots, attempts, answers, comments and scores retain their
        # original board ID. Only the current revision for November 4 changes.
        board = Daily.objects.using(alias).create(
            date=DAY, is_current=True, status='published', reveal_mode='instant',
            locale_seed=source['release'], published_at=timezone.now(), minimum_candidates=None,
            **{key: source[key] for key in ('author_name', 'author_url', 'author_description')},
        )
        for position, slot in enumerate(source['slots'], 1):
            row = Slot.objects.using(alias).create(
                daily_id=board.pk, position=position, role=slot['role'],
                label_pl=slot['label_pl'], label_en=slot['label_en'],
            )
            Condition.objects.using(alias).bulk_create([
                Condition(slot_id=row.pk, order=order, **condition)
                for order, condition in enumerate(slot['conditions'])
            ])


class Migration(migrations.Migration):
    dependencies = [
        ('dailies', '0027_restore_original_november_3'),
        ('players', '0007_verified_worlds_opponents'),
    ]
    operations = [
        migrations.AlterField(
            model_name='dailyslotcondition', name='condition_type',
            field=models.CharField(choices=[('role', 'Rola'), ('region', 'Region'), ('residency', 'Residency'), ('country', 'Kraj'), ('birth_country', 'Kraj urodzenia'), ('continent', 'Kontynent'), ('birth_continent', 'Kontynent urodzenia'), ('team', 'Drużyna'), ('team_year', 'Drużyna w konkretnym roku'), ('worlds_team_year', 'Drużyna i rok występu na Worlds'), ('league', 'Liga'), ('coach', 'Trener'), ('active', 'Aktywny / emerytowany'), ('birth_year_range', 'Rok urodzenia'), ('champion_played', 'Grał championem'), ('worlds_appearance', 'Występ na Worlds'), ('worlds_count_min', 'Min. liczba występów na Worlds'), ('worlds_debut_year', 'Debiut na Worlds'), ('worlds_last_year', 'Ostatni Worlds'), ('worlds_early_era', 'Worlds w erze S1-S3'), ('worlds_teams_min', 'Min. liczba organizacji na Worlds'), ('worlds_multi_role', 'Worlds na kilku rolach'), ('worlds_champion', 'Mistrz Worlds'), ('worlds_titles_min', 'Min. liczba tytułów Worlds'), ('worlds_final', 'Finał Worlds'), ('worlds_final_lost', 'Przegrany finał Worlds'), ('worlds_semifinal', 'Półfinał Worlds'), ('worlds_group_escape', 'Wyjście z grupy'), ('worlds_never_escaped', 'Nigdy nie wyszedł z grupy'), ('worlds_never_won', 'Nigdy nie wygrał Worlds'), ('worlds_playin', 'Przeszedł play-in'), ('pentakill_worlds', 'Pentakill na Worlds'), ('worlds_win_rate', 'Win rate na Worlds'), ('worlds_games', 'Liczba meczów na Worlds'), ('worlds_top5_champion', 'Champion w top 5 na Worlds'), ('career_top5_champion', 'Champion w top 5 kariery'), ('worlds_eliminated_stage', 'Etap odpadnięcia z Worlds'), ('worlds_playin_appearance', 'Udział w play-in Worlds'), ('country_excluded', 'Narodowość inna niż wskazana'), ('worlds_group_exit_before', 'Odpadnięcie w grupie przed rokiem'), ('career_regions_min', 'Min. liczba regionów kariery'), ('worlds_titles_exact', 'Dokładna liczba tytułów Worlds'), ('worlds_title_on_debut', 'Tytuł Worlds w debiucie'), ('worlds_final_lost_to_faker', 'Przegrany finał przeciwko Fakerowi'), ('european_masters_played', 'Udział w EU/EMEA Masters'), ('european_masters_won', 'Zwycięstwo w EU/EMEA Masters'), ('worlds_opponent_team', 'Rywal drużyny na Worlds przed 2026'), ('worlds_opponent_player', 'Rywal zawodnika na Worlds przed 2026'), ('worlds_beat_team', 'Wygrana mapa z drużyną na Worlds przed 2026'), ('worlds_beat_player', 'Wygrana mapa z zawodnikiem na Worlds przed 2026'), ('msi_appearance', 'Występ na MSI'), ('leagues_min', 'Min. liczba lig głównych'), ('wildcard_region', 'Region wildcard'), ('import_player', 'Import (gra poza swoim regionem)')], max_length=32),
        ),
        migrations.RunPython(install, migrations.RunPython.noop),
    ]
