# 🚀 Deployment Guide — LoL Kontra

## Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────┐
│   VERCEL (Frontend)         │     │   RENDER (Backend)        │
│   Next.js 14                │────▶│   Django + Gunicorn       │
│   https://xxx.vercel.app    │     │   https://xxx.onrender.com│
└─────────────────────────────┘     └───────────┬──────────────┘
                                                │
                                    ┌───────────▼──────────────┐
                                    │   NEON.TECH (Database)    │
                                    │   PostgreSQL (free tier)  │
                                    │   0.5 GB storage          │
                                    └──────────────────────────┘
```

**Cost: $0/month** (all free tiers)

---

## Step 1: Create Neon Database (free)

1. Go to [https://neon.tech](https://neon.tech) and sign up (GitHub login works)
2. Click **"New Project"**
   - Name: `lol-kontra`
   - Region: `Frankfurt (eu-central-1)` (closest to Render EU)
   - Click **Create**
3. Copy the **connection string** (looks like):
   ```
   postgresql://neondb_owner:xxxxxxx@ep-cool-name-12345.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. **Save it** — you'll need it for Render

**Free tier limits:**
- 0.5 GB storage (enough for thousands of players + daily results)
- 190 compute hours/month (auto-suspends after 5 min inactivity)
- Unlimited databases/projects

---

## Step 2: Deploy Backend to Render (free)

1. Go to [https://render.com](https://render.com) and sign up
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo (`Axword/lol-kontra`)
4. Configure:
   - **Name:** `lol-kontra-backend`
   - **Region:** `Frankfurt (EU)` (same as Neon)
   - **Branch:** `master`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `bash build.sh`
   - **Start Command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
   - **Plan:** `Free`

5. Add **Environment Variables:**

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | _(paste Neon connection string)_ |
   | `DB_SSL_REQUIRE` | `true` |
   | `DJANGO_SECRET_KEY` | _(generate random 50+ chars)_ |
   | `DJANGO_DEBUG` | `false` |
   | `DJANGO_ALLOWED_HOSTS` | `.onrender.com` |
   | `DJANGO_SETTINGS_MODULE` | `config.settings` |
   | `CORS_ALLOWED_ORIGINS` | `https://your-app.vercel.app` |
   | `CSRF_TRUSTED_ORIGINS` | `https://lol-kontra-backend.onrender.com` |
   | `RENDER` | `true` |
   | `PYTHON_VERSION` | `3.12.0` |

6. Click **"Create Web Service"**

7. After deploy, run migrations from the **Shell** (Render dashboard → Shell):
   ```bash
   python manage.py migrate
   python manage.py loaddata worlds_players_django
   python manage.py create_daily --publish
   ```

**Free tier notes:**
- Spins down after 15 min inactivity (first request takes ~30s to cold start)
- 750 hours/month free
- 512 MB RAM

---

## Step 3: Deploy Frontend to Vercel

1. Go to [https://vercel.com](https://vercel.com) and import the repo
2. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Next.js
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`

3. Add **Environment Variables:**

   | Variable | Value | Purpose |
   |----------|-------|---------|
   | `BACKEND_URL` | `https://lol-kontra-backend.onrender.com` | Backend URL for proxy rewrites |
   | `NEXT_PUBLIC_USE_API` | `true` | Enable API mode (proxied via Next.js) |

   **How it works:** The frontend calls `/api/v1/*` (same origin), Next.js proxies
   these to `BACKEND_URL/api/v1/*`. No CORS configuration needed!

   **Alternative (direct):** Set `NEXT_PUBLIC_API_URL=https://backend.onrender.com/api/v1`
   instead. This calls the backend directly (requires CORS setup on Render).

4. Click **Deploy**

---

## Step 4: Connect Frontend ↔ Backend

The frontend supports two modes:

### Mode A: Static (no backend needed)
- Data from pre-built JSON files in `/data/`
- Verification happens in browser
- Don't set any API environment variables

### Mode B: API via proxy (recommended)
- Data from Django API, proxied through Next.js
- Verification happens server-side (anti-cheat)
- Set on Vercel: `BACKEND_URL=https://xxx.onrender.com` + `NEXT_PUBLIC_USE_API=true`
- Set on Render: `CORS_ALLOWED_ORIGINS=https://xxx.vercel.app`
- No CORS issues (same-origin proxy)

### Mode C: API direct (simpler but needs CORS)
- Data from Django API, called directly from browser
- Set on Vercel: `NEXT_PUBLIC_API_URL=https://xxx.onrender.com/api/v1`
- Set on Render: `CORS_ALLOWED_ORIGINS=https://xxx.vercel.app`

**Switch between modes** by setting/unsetting the env vars and redeploying.

---

## API Endpoints (Backend)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dailies/today/` | GET | Today's daily challenge |
| `/api/v1/dailies/{id}/` | GET | Specific daily |
| `/api/v1/players/` | GET | All players (paginated) |
| `/api/v1/players/autocomplete/?q=fak` | GET | Search players |
| `/api/v1/submissions/answer/` | POST | Verify a pick (instant) |
| `/api/v1/scoring/dailies/{id}/answer-stats/` | GET | Answer statistics |
| `/api/v1/scoring/dailies/{id}/score-distribution/` | GET | Score distribution |

---

## Local Development

### Docker (full stack)
```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/api/docs/
```

### Frontend only (static mode)
```bash
cd frontend
npm install
npm run dev
# http://localhost:3000 (uses static JSON data)
```

### Backend only (local)
```bash
cd backend
pip install -r requirements.txt
# Set DATABASE_URL to your Neon URL for testing against prod data
export DATABASE_URL=postgresql://...
python manage.py migrate
python manage.py runserver
# http://localhost:8000
```

---

## Database Management (Neon)

### Run migrations
```bash
# From local machine, set DATABASE_URL and run:
export DATABASE_URL=postgresql://neondb_owner:xxx@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
cd backend
python manage.py migrate
python manage.py loaddata worlds_players_django
python manage.py create_daily --publish
```

### Seed players from fixture
```bash
python manage.py loaddata worlds_players_django
# Or use the management command:
python manage.py seed_players --full
```

### Create daily challenge
```bash
python manage.py create_daily --publish
```

### Neon branching (bonus feature!)
Neon lets you create instant database branches for testing:
```bash
neonctl branches create --name dev-testing
# Migrate + seed the branch without affecting production
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend cold start slow | Normal for Render free tier (~30s first request) |
| Neon connection timeout | Database auto-suspended; first query wakes it (~2s) |
| CORS errors | Check `CORS_ALLOWED_ORIGINS` includes your Vercel URL |
| SSL errors with Neon | Set `DB_SSL_REQUIRE=true` in Render env vars |
| `django_celery_beat` not found | Set `RENDER=true` env var to skip celery apps |
| Static files 404 | Run `python manage.py collectstatic` on Render |

---

## Optional Upgrades

| Service | Free → Paid | When to upgrade |
|---------|-------------|-----------------|
| Render | Free → Starter ($7/mo) | Need always-on, no cold starts |
| Neon | Free → Launch ($19/mo) | Need >0.5GB or no auto-suspend |
| Vercel | Hobby → Pro ($20/mo) | Team features or >100GB bandwidth |
