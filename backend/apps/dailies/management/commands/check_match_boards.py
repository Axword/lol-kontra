"""Read-only match board preview. This command never publishes or rewrites a board."""
from django.core.management.base import BaseCommand, CommandError

from apps.dailies.match_boards import audit_match_board, load_plan
from apps.players.models import Player


class Command(BaseCommand):
    help = 'Preview and validate upcoming match boards without writing any games or requirements'

    def add_arguments(self, parser):
        parser.add_argument('--date', help='Preview one YYYY-MM-DD match')

    def handle(self, *args, **options):
        players = list(Player.objects.all().order_by('slug'))
        try:
            matches = [m for m in load_plan()['matches'] if not options['date'] or m['date'] == options['date']]
            if not matches:
                raise ValueError('No match planned for this date')
            for match in matches:
                self.stdout.write(f"{match['date']} | {match['description_pl']} | {match['review_status']}")
                if match['review_status'] == 'pending_matchup':
                    self.stdout.write('Przeciwnicy nie są jeszcze potwierdzeni; bez automatycznej publikacji.')
                    continue
                pools = audit_match_board(match, players)
                for slot, pool in zip(match['slots'], pools):
                    text = ' + '.join(condition['label_pl'] for condition in slot['conditions'])
                    self.stdout.write(f"  {slot['role']}: {text} [{len(pool)} odpowiedzi]")
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise CommandError(str(error)) from error
