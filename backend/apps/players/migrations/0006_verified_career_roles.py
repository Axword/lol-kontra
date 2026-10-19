"""Add verified professional career roles; never rewrite saved gameplay.

The original release remains immutable. This additive correction has its own
pinned evidence and updates only secondary_roles for its canonical identity.
"""
from hashlib import sha256
import json
from pathlib import Path

from django.db import migrations, transaction


SOURCE_FILE = 'career_roles_2026_10_19_v1.json'
SOURCE_SHA256 = '76d3bf698c138700f361f910550ebbef92f7f8aba9dd627bd9840dbcf80090db'
ROLE_ORDER = ('top', 'jungle', 'mid', 'adc', 'support')


def load_corrections():
    # Normalize Git CRLF checkouts before checking the immutable UTF-8 evidence.
    payload = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / SOURCE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError('Career role evidence checksum mismatch')
    document = json.loads(payload)
    return document['corrections']


def install_correction(apps, schema_editor):
    corrections = load_corrections()
    Player = apps.get_model('players', 'Player')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        # Only non-key role data changes. Allow concurrent answers to retain
        # their FK KEY SHARE locks without a cross-player deployment deadlock.
        existing = {player.slug: player for player in Player.objects.using(alias).select_for_update(no_key=True)
                    .filter(slug__in=[row['slug'] for row in corrections]).order_by('pk')}
        updates = []
        for correction in corrections:
            player = existing.get(correction['slug'])
            if player is None:
                continue
            if player.attributes.get('leaguepedia_page') != correction['leaguepedia_page']:
                raise ValueError(f"Career role correction conflicts with canonical identity: {correction['slug']}")
            roles = set(player.secondary_roles or []) | set(correction['roles'])
            roles.discard(player.primary_role)
            secondary_roles = sorted(roles, key=ROLE_ORDER.index)
            if secondary_roles != player.secondary_roles:
                updates.append((player.pk, secondary_roles))
        # Validate every canonical identity before the first database write.
        for pk, secondary_roles in updates:
            Player.objects.using(alias).filter(pk=pk).update(secondary_roles=secondary_roles)


class Migration(migrations.Migration):
    dependencies = [('players', '0005_worlds_2026_october_19_release')]
    # Removing verified career knowledge on rollback could invalidate already
    # accepted choices. Historical answers are deliberately never revisited.
    operations = [migrations.RunPython(install_correction, migrations.RunPython.noop)]
