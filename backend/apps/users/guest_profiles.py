"""Guest identity and conservative local nickname moderation.

This filter handles common Polish/English profanity and simple obfuscation.
Short ambiguous words are matched whole; clear severe roots also match inside
decorated names. It is not a guarantee against every offensive nickname.
"""
import hashlib
import hmac
import re
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import serializers

from apps.submissions.models import MAX_ERRORS, Submission


_BLOCKED_WORDS = frozenset('''
    kurwa kurwy kurwo kurwie kurwami kurwiszon skurwysyn skurwiel
    chuj chuja chuju chuje chujem chujowy chujowa chujowe huj huja huju
    cipa cipy cipo cipka pizda pizdy pizdo
    jebac jebany jebana jebane jebani jebie jebiesz jebal jebala jebali
    pojeb pojebany pojebana zjeb zjebany zjebana
    pierdol pierdole pierdolic pierdolisz pierdolenie pierdolony
    wypierdalaj spierdalaj wypierdalac spierdalac zapierdalac japierdole
    suka suki suko debil debilu idiota idiot idiots
    fuck fucker fuckers fucking fuckyou motherfucker motherfuckers
    shit shitty bullshit bitch bitches asshole assholes cunt cunts dick twat
    nigger niggers nigga niggas faggot faggots retard retarded
    hitler nazi heilhitler
'''.split())
_LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't',
                      'ł': 'l', 'а': 'a', 'е': 'e', 'о': 'o', 'с': 'c', 'і': 'i',
                      'у': 'y', 'х': 'x', 'к': 'k'})


def guest_identity_key(token):
    return hmac.new(settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def guest_display_name(token, nickname=''):
    return f"Gość-{nickname or guest_identity_key(token)[:8].upper()}"


def _moderation_forms(value):
    folded = unicodedata.normalize('NFKD', value.casefold())
    folded = ''.join(char for char in folded if not unicodedata.combining(char))
    # Keep individual words and the joined form, catching both "fuck you" and
    # "k_u_r_w_a" without substring-matching innocent names such as Scunthorpe.
    parts = re.findall(r'[^\W_]+', folded, flags=re.UNICODE)
    candidates = [*parts, ''.join(parts)]
    forms = set()
    for candidate in candidates:
        for item in (candidate, candidate.strip('0123456789')):
            item = item.translate(_LEET)
            forms.update((item, re.sub(r'(.)\1+', r'\1', item)))
    return forms


_BLOCKED_FORMS = frozenset(form for word in _BLOCKED_WORDS for form in _moderation_forms(word))
_SEVERE_ROOT = re.compile(
    r'k+u+r+w+a+|s+k+u+r+w+|p+i+e+r+d+o+l+|f+u+c+k+'
    r'|n+i+g{2,}e+r+|n+i+g{2,}a+|f+a+g{2,}o+t+'
)


def validate_guest_nickname(value):
    if not isinstance(value, str):
        raise serializers.ValidationError('Nick musi być tekstem.')
    if len(value) > 256 or any(unicodedata.category(char).startswith('C') for char in value):
        raise serializers.ValidationError('Nick zawiera niedozwolone znaki.')
    normalized = unicodedata.normalize('NFKC', value)
    normalized = ' '.join(normalized.split())
    if not normalized:
        return ''
    if not 3 <= len(normalized) <= 24:
        raise serializers.ValidationError('Nick musi mieć od 3 do 24 znaków.')
    if any(not (unicodedata.category(char)[0] in 'LN' or char in ' _-') for char in normalized):
        raise serializers.ValidationError('Użyj liter, cyfr, spacji, myślnika lub podkreślenia.')
    if not any(unicodedata.category(char)[0] in 'LN' for char in normalized):
        raise serializers.ValidationError('Nick musi zawierać literę lub cyfrę.')
    forms = _moderation_forms(normalized)
    if forms & _BLOCKED_FORMS or any(_SEVERE_ROOT.search(form) for form in forms):
        raise serializers.ValidationError('Wybierz nick bez obraźliwych słów.')
    return normalized


def guest_stats(token):
    """Derive stats from existing finished games; naming never creates votes."""
    games = list(Submission.objects.filter(
        user__isnull=True, guest_token=token, is_practice=False, is_seed=False,
        daily__date__lte=timezone.localdate(), daily__status__in=['published', 'closed', 'scored'],
    ).annotate(
        slot_count=Count('daily__slots', distinct=True),
        correct_count=Count('answers', filter=Q(answers__is_correct=True), distinct=True),
    ).filter(
        Q(is_scored=True) | Q(errors_used__gte=MAX_ERRORS)
        | Q(slot_count__gt=0, correct_count__gte=F('slot_count'))
    ).select_related('daily').prefetch_related('answers').order_by('daily__date'))
    total = sum(game.total_points for game in games)
    answers = [answer for game in games for answer in game.answers.all() if answer.is_correct]
    streak = longest = 0
    previous = None
    for game in games:
        streak = streak + 1 if previous and game.daily.date == previous + timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = game.daily.date
    return {
        'games_played': len(games),
        'total_points': total,
        'avg_points': total / len(games) if games else 0,
        'best_score': max((game.total_points for game in games), default=0),
        'legendary_answers': sum(answer.rarity_tier == 'legendary' for answer in answers),
        'diamond_picks': sum(answer.is_diamond_pick for answer in answers),
        'current_streak': streak if previous and previous >= timezone.localdate() - timedelta(days=1) else 0,
        'max_streak': longest,
    }
