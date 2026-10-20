"""Bounded, server-rendered snapshots of a player's saved, finished roster."""
from io import BytesIO
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from unidecode import unidecode

from apps.players.serializers import VerifiedPlayerSerializer


MAX_ROSTER_BYTES = 256000
MAX_PORTRAIT_BYTES = 1_000_000
_PORTRAIT_HOSTS = {'static.wikia.nocookie.net', 'vignette.wikia.nocookie.net'}
_COLORS = {
    'common': ('#ffffff', '#d7ded8'), 'uncommon': ('#dcf5df', '#8cc49b'),
    'rare': ('#dcecff', '#8caddb'), 'epic': ('#eadbff', '#b394d8'),
    'legendary': ('#ffea98', '#dec366'),
}
_POSITIONS = {'top': (18, 66), 'jungle': (78, 217), 'mid': (284, 126),
              'adc': (508, 270), 'support': (288, 390)}


def _font(size):
    return ImageFont.load_default(size=size)


def _safe_text(text, length=22):
    # The bundled Pillow font is reproducible on Windows and the slim Docker
    # image. Player identities remain unchanged in the API; romanization here
    # avoids a missing-glyph box for a rare non-Latin nickname in the raster.
    value = unidecode(str(text))
    return value if len(value) <= length else value[:length - 3] + '...'


def load_player_portrait(player):
    url = VerifiedPlayerSerializer().get_portrait_url(player)
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.hostname not in _PORTRAIT_HOSTS:
        return None
    try:
        deadline = monotonic() + 2.0
        # Redirects are deliberately disabled: a trusted CDN URL must never
        # redirect this server to an arbitrary hostname or local address.
        with httpx.stream('GET', url, follow_redirects=False,
                          timeout=httpx.Timeout(1.5, connect=1.0)) as response:
            if response.status_code != 200:
                return None
            value = bytearray()
            for chunk in response.iter_bytes():
                value.extend(chunk)
                if len(value) > MAX_PORTRAIT_BYTES or monotonic() > deadline:
                    return None
        with Image.open(BytesIO(value)) as candidate:
            if candidate.width * candidate.height > 4_000_000:
                return None
            candidate.verify()
        with Image.open(BytesIO(value)) as candidate:
            return ImageOps.fit(candidate.convert('RGB'), (42, 48), centering=(.5, .15))
    except (httpx.HTTPError, OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None


def render_roster_png(submission):
    image = Image.new('RGB', (720, 500), '#102d25')
    map_path = Path(__file__).resolve().parents[2] / 'assets' / 'rift-map.png'
    with Image.open(map_path) as map_image:
        image.paste(map_image.convert('RGB').resize((480, 480), Image.Resampling.LANCZOS), (120, 10))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 720, 43), fill='#ffffff')
    draw.text((18, 12), 'WORLDS KONTRA', fill='#17291f', font=_font(21))
    score = f'{submission.total_points:.2f}'.rstrip('0').rstrip('.')
    draw.text((505, 13), f'Wynik: {score}', fill='#215f4e', font=_font(18))
    answers = {answer.daily_slot_id: answer for answer in submission.answers.filter(
        is_correct=True).select_related('player', 'daily_slot')}
    for slot in submission.daily.slots.order_by('position'):
        x, y = _POSITIONS[slot.role]
        answer = answers.get(slot.pk)
        diamond = answer is not None and answer.is_diamond_pick
        background, border = ('#ddf6ff', '#47b8d8') if diamond else _COLORS.get(
            answer.rarity_tier if answer else None, ('#153a2e', '#658474'))
        text_color = '#183325' if answer else '#ffffff'
        draw.rectangle((x, y, x + 194, y + 90), fill=background, outline=border, width=3 if diamond else 1)
        draw.text((x + 61, y + 10), slot.role.upper(), fill=text_color, font=_font(11))
        draw.text((x + 61, y + 29), _safe_text(answer.player.nickname if answer else '---', 18),
                  fill=text_color, font=_font(15))
        portrait = load_player_portrait(answer.player) if answer else None
        if portrait:
            image.paste(portrait, (x + 10, y + 10))
        else:
            draw.rectangle((x + 10, y + 10, x + 51, y + 57), outline=border, width=1)
            draw.text((x + 22, y + 25), _safe_text(answer.player.nickname[:1] if answer else '?'),
                      fill=text_color, font=_font(17))
        if answer:
            percent = answer.rarity_percent
            label = f'{percent:.2f}'.rstrip('0').rstrip('.') + '%' if percent is not None else '--%'
            draw.text((x + 13, y + 68), label, fill='#215f4e', font=_font(12))
            if diamond:
                draw.polygon([(x + 166, y + 65), (x + 178, y + 65), (x + 183, y + 70),
                              (x + 172, y + 81), (x + 161, y + 70)], outline='#1985aa', width=2)
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    value = output.getvalue()
    if not value.startswith(b'\x89PNG\r\n\x1a\n') or len(value) > MAX_ROSTER_BYTES:
        raise ValueError('Roster snapshot exceeds its safe image size')
    return value


def localize_roster_png(value, locale):
    """Translate the header of an immutable snapshot without changing its score or roster."""
    with Image.open(BytesIO(value)) as stored:
        image = stored.convert('RGB')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 490, 43), fill='#ffffff')
    draw.text((18, 12), 'WORLDS KONTRA', fill='#17291f', font=_font(21))
    # Stored snapshots use this exact Polish label. Leave the numeric score at
    # its original coordinates, even if the game's live score has since changed.
    font = _font(18)
    end = 505 + int(draw.textlength('Wynik: ', font=font)) - 1
    draw.rectangle((505, 0, end, 43), fill='#ffffff')
    draw.text((505, 13), 'Score:' if locale == 'en' else 'Wynik:', fill='#215f4e', font=font)
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()
