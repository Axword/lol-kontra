"""
Import career champion stats from lol.fandom.com into the database.

Usage:
    python manage.py import_career_stats --player Faker
    python manage.py import_career_stats --all-worlds-players
    python manage.py import_career_stats --from-json career_stats.json
"""
import json
import sys
from django.core.management.base import BaseCommand
from apps.players.models import Player, CareerChampionStat


class Command(BaseCommand):
    help = 'Import career champion stats from lol.fandom.com'

    def add_arguments(self, parser):
        parser.add_argument('--player', type=str, help='Import stats for a single player (by nickname or slug)')
        parser.add_argument('--all-worlds-players', action='store_true', help='Import stats for all players in DB')
        parser.add_argument('--from-json', type=str, help='Import from JSON file instead of scraping')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of players to process (0 = all)')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without saving')

    def handle(self, *args, **options):
        if options['from_json']:
            self.import_from_json(options['from_json'], options['dry_run'])
        elif options['player']:
            self.import_single_player(options['player'], options['dry_run'])
        elif options['all_worlds_players']:
            self.import_all_players(options['limit'], options['dry_run'])
        else:
            self.stderr.write("Specify --player, --all-worlds-players, or --from-json")
            sys.exit(1)

    def import_single_player(self, player_id, dry_run):
        try:
            player = Player.objects.get(slug=player_id)
        except Player.DoesNotExist:
            try:
                player = Player.objects.get(nickname__iexact=player_id)
            except Player.DoesNotExist:
                self.stderr.write(f"Player not found: {player_id}")
                return

        from scraper.leaguepedia.career_stats import fetch_player_career_stats
        lolpedia_name = player.nickname.replace(' ', '_')
        stats = fetch_player_career_stats(lolpedia_name)

        if not stats:
            self.stdout.write(f"No stats found for {player.nickname}")
            return

        if not dry_run:
            created, updated = self._upsert_stats(player, stats)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {player.nickname}: {len(stats)} champions "
                    f"(created={created}, updated={updated})"
                )
            )
        else:
            self.stdout.write(f"[dry-run] Would import {len(stats)} champions for {player.nickname}")

    def import_all_players(self, limit, dry_run):
        from scraper.leaguepedia.career_stats import fetch_player_career_stats

        qs = Player.objects.filter(worlds_count__gt=0).order_by('-worlds_count')
        if limit > 0:
            qs = qs[:limit]

        total = qs.count() if not limit else min(limit, qs.count())
        created_total, updated_total = 0, 0

        for i, player in enumerate(qs, 1):
            self.stdout.write(f"[{i}/{total}] {player.nickname}...")
            lolpedia_name = player.nickname.replace(' ', '_')
            stats = fetch_player_career_stats(lolpedia_name)

            if not stats:
                continue

            if not dry_run:
                created, updated = self._upsert_stats(player, stats)
                created_total += created
                updated_total += updated

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total: created={created_total}, updated={updated_total}"
            )
        )

    def import_from_json(self, path, dry_run):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        created_total, updated_total = 0, 0

        for player_name, stats in data.items():
            try:
                player = Player.objects.get(nickname__iexact=player_name)
            except Player.DoesNotExist:
                try:
                    player = Player.objects.get(slug=player_name.lower().replace(' ', '-'))
                except Player.DoesNotExist:
                    self.stdout.write(f"  [skip] Player not found: {player_name}")
                    continue

            if not dry_run:
                created, updated = self._upsert_stats(player, stats)
                created_total += created
                updated_total += updated
                self.stdout.write(f"  {player.nickname}: {len(stats)} champions (c={created}, u={updated})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported from {path}: created={created_total}, updated={updated_total}"
            )
        )

    def _upsert_stats(self, player, stats_list):
        """Upsert career champion stats using bulk operations."""
        FIELDS = [
            'games_played', 'games_won', 'games_lost', 'win_ratio',
            'kills', 'deaths', 'assists', 'kda', 'cs_per_min', 'dmg_per_min',
        ]

        existing = {
            s.champion_name: s
            for s in CareerChampionStat.objects.filter(player=player, source='lolwiki')
        }

        to_create, to_update = [], []
        for stat_data in stats_list:
            champ = stat_data['champion_name']
            if champ in existing:
                obj = existing[champ]
                changed = False
                for f in FIELDS:
                    new_val = stat_data.get(f)
                    if new_val is not None and getattr(obj, f) != new_val:
                        setattr(obj, f, new_val)
                        changed = True
                if changed:
                    to_update.append(obj)
            else:
                to_create.append(CareerChampionStat(
                    player=player,
                    champion_name=champ,
                    source='lolwiki',
                    **{f: stat_data.get(f, 0) or 0 for f in FIELDS if f in stat_data}
                ))

        if to_create:
            CareerChampionStat.objects.bulk_create(to_create)
        if to_update:
            CareerChampionStat.objects.bulk_update(to_update, FIELDS)

        return len(to_create), len(to_update)
