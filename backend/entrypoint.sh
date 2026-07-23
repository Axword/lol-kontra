#!/bin/sh
set -e

# === LoL Roster Challenge – Docker Entrypoint ===
# Automatycznie: migracje, fixtures, daily, collectstatic

echo ""
echo "  __      __       _     _       __  __ ___ "
echo "  \ \    / /__  _ _| |__| |___   \ \/ /|_ _|"
echo "   \ \/\/ / _ \| '_| / _\` / -_)  >  <  | | "
echo "    \_/\_/\___/|_| |_\__,_\___| /_/\_\|___|"
echo ""
echo "== LoL Roster Challenge – starting =="
echo ""

# --- wait for PostgreSQL ---
echo "⏳ Waiting for PostgreSQL at $POSTGRES_HOST:${POSTGRES_PORT:-5432} ..."
attempt=0
max_attempts=30
until python - << 'PY'
import os, sys, psycopg2
try:
    conn = psycopg2.connect(
        dbname=os.getenv('POSTGRES_DB','lolroster'),
        user=os.getenv('POSTGRES_USER','lolroster'),
        password=os.getenv('POSTGRES_PASSWORD','lolroster'),
        host=os.getenv('POSTGRES_HOST','db'),
        port=os.getenv('POSTGRES_PORT','5432'),
        connect_timeout=2
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
do
  attempt=$((attempt+1))
  if [ $attempt -ge $max_attempts ]; then
    echo "❌ PostgreSQL still not ready after $max_attempts attempts – continuing anyway"
    break
  fi
  echo "  postgres not ready – try $attempt/$max_attempts – sleep 2s"
  sleep 2
done
echo "✅ PostgreSQL ready"

# --- wait for Redis ---
echo "⏳ Checking Redis at ${REDIS_URL:-redis://redis:6379/0} ..."
python - << 'PY' || true
import os, sys
try:
    import redis
    r = redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'), socket_connect_timeout=2)
    r.ping()
    print("✅ Redis ready")
except Exception as e:
    print(f"⚠️  Redis not ready (will retry later): {e}")
PY

# --- Django setup ---
echo ""
echo "📦 Django setup..."
# BUG FIX: Never run makemigrations in production – only apply existing migrations
python manage.py migrate --noinput

# --- Fixtures: players ---
echo ""
echo "🎮 Checking player fixtures..."
PLAYER_COUNT=$(python manage.py shell -c "from apps.players.models import Player; print(Player.objects.count())" 2>/dev/null | tail -n1)
echo "   Players in DB: ${PLAYER_COUNT:-0}"
if [ "${PLAYER_COUNT:-0}" -lt 100 ]; then
  echo "📥 Loading Worlds players fixture (876 players)..."
  # try loaddata first (fastest)
  if python manage.py loaddata worlds_players_django 2>/dev/null; then
    echo "✅ loaddata worlds_players_django – OK"
  else
    echo "  loaddata failed, trying seed_players --full ..."
    python manage.py seed_players --full || python manage.py seed_players --sample || true
  fi
else
  echo "✅ Players already seeded ($PLAYER_COUNT) – skipping"
fi

# --- ScoringConfig ensure ---
python manage.py shell << 'PY' || true
from apps.scoring.models import ScoringConfig
cfg, created = ScoringConfig.objects.get_or_create(is_active=True, defaults={
  'points_common':10,'points_rare':25,'points_epic':60,'points_legendary':120,'diamond_bonus':50
})
print(f"ScoringConfig: {'created' if created else 'exists'} id={cfg.id}")

# force instant reveal mode – product decision 2026-07-07
from apps.dailies.models import Daily
updated = Daily.objects.exclude(reveal_mode='instant').update(reveal_mode='instant')
if updated: print(f"Updated {updated} dailies to reveal_mode=instant")
PY

# --- Daily ensure ---
echo ""
echo "📅 Ensuring today Daily exists..."
python manage.py create_daily --publish || true

# --- static files (prod) ---
if [ "$DJANGO_DEBUG" != "true" ] && [ "$DJANGO_DEBUG" != "True" ]; then
  echo "📦 Collecting static files..."
  python manage.py collectstatic --noinput || true
fi

# --- show summary ---
echo ""
python manage.py shell << 'PY'
from apps.players.models import Player
from apps.dailies.models import Daily
from django.utils import timezone
print("="*52)
print(f"  PLAYERS: {Player.objects.count()}")
print(f"  ACTIVE : {Player.objects.filter(is_active=True).count()}")
try:
    d = Daily.objects.get(date=timezone.localdate())
    print(f"  TODAY  : Daily #{d.id} – {d.date} – {d.status} – slots:{d.slots.count()}")
except Exception as e:
    print(f"  TODAY  : not ready – {e}")
print("="*52)
PY

echo ""
echo "🚀 Starting: $@"
echo ""
exec "$@"
