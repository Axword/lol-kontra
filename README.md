# League of Legends Esports Roster Challenge – Worlds XI

Codzienna gra LoL Esports inspirowana [kontra.games „Mundialowa Jedenastka”](https://kontra.games/pl/graj/mundialowa-jedenastka/7).

**Stack:** Next.js 14 + TypeScript + Tailwind — **100% frontend, zero backendu.**

Wszystkie dane gry (baza 876 graczy Worlds + codzienne zagadki) są generowane
**podczas builda** do statycznych plików JSON. Weryfikacja odpowiedzi i punktacja
odbywają się lokalnie w przeglądarce, a postępy zapisywane są w `localStorage`.

## Jak to działa

```
frontend/
├── data/players.source.json      # źródłowa baza 876 graczy Worlds S1–S15
├── scripts/generate-data.mjs     # generator – uruchamiany w prebuild/predev
└── public/data/                  # (generowane, w .gitignore)
    ├── players.json              # odchudzona baza do wyszukiwarki
    ├── index.json                # lista dostępnych dni (archiwum + przyszłość)
    └── dailies/<id>.json         # 1 plik = 1 zagadka: 5 slotów, warunki,
                                  # poprawne odpowiedzi + pick% + diamond
```

Generator jest **deterministyczny względem daty** (seedowany PRNG) – każdy build
tworzy identyczne zagadki dla tych samych dni. Jeden build zawiera ~60 dni
archiwum + ~200 dni w przód, więc aplikacja „sama” serwuje nową zagadkę
każdego dnia bez re-deployu.

## Zasady gry (styl kontra.games)

- 5 slotów (Top / Jungle / Mid / ADC / Support), każdy z 2–3 warunkami
  (np. „Koreańczyk” + „Wygrał Worlds”).
- Wybór weryfikowany **natychmiast** – trafienie blokuje slot, błąd zabiera życie (max 10).
- Start **500 pkt**, każde trafienie odejmuje `100 − pick%`.
  **Niższy wynik = lepszy.** Najrzadszy poprawny pick w slocie = 💎 Diamond (-100).
- Archiwum – można grać wszystkie poprzednie dni.
- **Pytania o picki (signature champion):** warunki slotów mogą zawierać
  „Często grał na X” – dane o najczęściej granych championach pochodzą z bazy
  (`top_champions_career` w `frontend/data/players.source.json`).

### Jakość danych

- Baza graczy jest **deduplikowana po slugu** przy generacji – ten sam zawodnik
  zapisywany wielokrotnie ( raz z pełnymi danymi, raz jako „śmieciowy” rekord z
  pustym wiekiem/błędnym krajem) pojawiał się w wyszukiwarce kilka razy i
  psuł warunki wiekowo-regionowe. Scalanie zachowuje rekord z największą
  kompletnością i uzupełnia braki.
- Nazwy są czyszczone z encji HTML (np. `&amp;nbsp;`).

## Szybki start

### Docker (nic poza Dockerem nie jest potrzebne)

```bash
docker compose up --build
# -> http://localhost:3000
```

Obraz jest wielostopniowy: instaluje zależności, generuje dane gry
(`prebuild` → `generate-data.mjs`), buduje Next.js w trybie `standalone`
i kopiuje do finalnego obrazu wyłącznie serwer, `public/` oraz statyki –
bez `node_modules` z etapu budowania. Kontener startuje jako użytkownik bez
uprawnień roota, na systemie plików tylko do odczytu, bez żadnych zmiennych
środowiskowych i bez bazy danych.

Inny port: `PORT=8080 docker compose up --build`.

**Ważne:** obraz zawiera zagadki na ~60 dni wstecz i ~200 dni w przód od dnia,
w którym został zbudowany. Po tym oknie trzeba go przebudować
(`docker compose build --no-cache && docker compose up -d`), inaczej gra
przestanie mieć nowe dni.

Sam obraz, bez compose:

```bash
docker build -t worlds-xi ./frontend
docker run --rm -p 3000:3000 worlds-xi
```

### Lokalnie, bez Dockera

```bash
cd frontend
npm install
npm run dev        # predev automatycznie generuje public/data/
# -> http://localhost:3000
```

## Deploy na Vercel

1. Zaimportuj repozytorium w [vercel.com/new](https://vercel.com/new).
2. Ustaw **Root Directory: `frontend`** (framework: Next.js wykryje się sam).
3. Deploy — `npm run build` sam wygeneruje dane gry (hook `prebuild`).

Nic więcej nie jest potrzebne – brak bazy danych, env vars i backendu.

Ewentualne odświeżenie danych: wystarczy re-deploy (np. cron w Vercel
„Deploy Hooks” raz w miesiącu), by wydłużyć okno wygenerowanych dni.

## Komendy

```bash
# w katalogu frontend/
npm run dev            # dev server (z generacją danych)
npm run build          # produkcyjny build (z generacją danych)
npm run generate-data  # sama generacja public/data/
npm run lint

# w katalogu głównym – skróty do Dockera
make up                # build + start w tle -> http://localhost:3000
make down              # zatrzymaj
make logs              # podgląd logów
make data              # przegeneruj public/data lokalnie (nowe okno dni)
make clean             # zatrzymaj i usuń obraz
```

## Struktura repo

- `frontend/` – cała aplikacja (Next.js 14 App Router)
- `frontend/Dockerfile` – produkcyjny obraz gry (multi-stage, `output: standalone`)
- `docker-compose.yml` – jedna usługa: gra
- `docker-compose.legacy.yml` – stary stos Django/PostgreSQL/Redis/Celery/nginx
- `backend/`, `scraper/`, `worker/` – **legacy** – stary stack Django/Celery,
  niepotrzebny do działania gry; źródło danych (`worlds_players_full.json`)
  zostało skopiowane do `frontend/data/players.source.json`

Licencja: MIT (do ustalenia) • Dane: Leaguepedia • Not affiliated with Riot Games
