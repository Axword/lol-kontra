# Vercel + Render + Neon

Instrukcja dotyczy działających usług: [frontendu](https://lol-kontra.vercel.app) i Django API `https://lol-kontra.onrender.com/api/v1`. Dla commita `e686188` Render potwierdził Live (`dep-dbajr4u7bikc73etp5s0`, 2 min 05 s), a Vercel Production Ready (`GJrFKwDfGcHMdYQA7kjy6p6bZHWh`, 59 s). W Chrome sprawdzono jasny interfejs, planszę oraz podpowiedź Fakera ze zdjęciem.

## Frontend w Vercelu

| Ustawienie | Wartość |
| --- | --- |
| Production Branch | `master` |
| Root Directory | `frontend` |
| Framework | Next.js |
| Install / Build Command | `npm ci` / `npm run build` |
| `NEXT_PUBLIC_API_URL` | `https://lol-kontra.onrender.com/api/v1`, Production i Preview |

Po zmianie `NEXT_PUBLIC_API_URL` potrzebny jest nowy build frontendu. Podglądy Vercela mają ten sam adres API, ale ich własne originy trzeba osobno dopisać w CORS/CSRF backendu; wildcardy nie są dozwolone.

## Istniejąca usługa Render

Edytuj istniejący Web Service `lol-kontra` (`srv-d9h4r5mrnols73elrbeg`), bez tworzenia kolejnej usługi:

| Ustawienie | Wartość |
| --- | --- |
| Branch | `master` |
| Runtime | Docker |
| Root Directory | `backend` |
| Dockerfile Path | `./Dockerfile.render` względem Root Directory |
| Docker Build Context | `.` względem Root Directory |
| Health Check Path | `/healthz/` |
| `WEB_CONCURRENCY` | `1` |

Panel może wyświetlać ścieżki z prefiksem `backend/`; nie dodawaj go ponownie, jeśli pole jest już względne wobec Root Directory. Pozostaw domyślne ENTRYPOINT/CMD obrazu. Przy starcie wykonują `bootstrap_database`, kontrolę danych i uprawnień oraz `collectstatic`, a dopiero potem uruchamiają Gunicorn na porcie z `PORT`. Błąd inicjalizacji zatrzymuje start.

## Zmienne backendu

Do prywatnego środowiska Rendera bezpiecznie zaimportowano 18 kluczy z lokalnego payloadu ignorowanego przez Git. Przy odtwarzaniu konfiguracji użyj poniższych ustawień; nie zapisuj payloadu ani wartości sekretów w repozytorium lub logach.

| Zmienna | Wartość lub źródło |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Osobny losowy sekret, co najmniej 50 znaków |
| `DJANGO_ALLOWED_HOSTS` | `lol-kontra.onrender.com` |
| `DJANGO_TRUST_PROXY_HEADERS` | `true`, dla proxy HTTPS Rendera |
| `CORS_ALLOWED_ORIGINS` | `https://lol-kontra.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://lol-kontra.vercel.app` |
| `DATABASE_URL` | Wygenerowany przez Neon URL pooled; zachowaj opcje TLS |
| `DATABASE_URL_UNPOOLED` | Bezpośredni URL właściciela do migracji i sesyjnej blokady wydania |
| `DATABASE_RUNTIME_URL` | URL ograniczonej roli aplikacji, na tej samej gałęzi i bazie Neon |
| `POSTGRES_APP_USER` | Użytkownik z `DATABASE_RUNTIME_URL` |
| `POSTGRES_APP_PASSWORD` | Hasło tego samego użytkownika |
| `REDIS_URL` | Wewnętrzny URL Key Value skopiowany z panelu Rendera: `<internal-redis-url>` |
| `WEB_CONCURRENCY` | `1` |

Właściciel bazy służy do migracji, a ograniczona rola do ruchu API. Dane `POSTGRES_APP_*` muszą zgadzać się z `DATABASE_RUNTIME_URL`; bootstrap sprawdza uprawnienia. Nie wpisuj pustych wartości URL ani danych Neon do `NEXT_PUBLIC_*`. Szczegóły podziału połączeń i przechowywania sekretów opisuje [NEON.md](NEON.md).

## Cache i zadania w tle

Free Key Value `lol-kontra-cache` we Frankfurcie działa: 25 MB, limit 50 połączeń, dostęp prywatny bez ruchu zewnętrznego. Backend używa wewnętrznego URL w `REDIS_URL`; publiczne zapytania API korzystające z PostgreSQL i Redisa zwróciły HTTP 200. Nie zastępuj połączenia adresem publicznym.

Zwykła rozgrywka działa przez API bez workera Celery. Administracyjne przeliczanie wyników i nocna finalizacja wymagają osobnego workera oraz schedulera z tym samym środowiskiem i właściwymi `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`. Te procesy nie zostały dotąd wdrożone. Nie utworzono płatnych zasobów.

## Sprawdzenie po wdrożeniu

Backend ma WhiteNoise do plików statycznych oraz `/healthz/` sprawdzający żywotność procesu bez zapytań do PostgreSQL ani Redisa. Pełny zestaw backendu przeszedł na odizolowanej lokalnej bazie testowej: 431 testów, 175 ostrzeżeń, 187,48 s. Frontend: 119 testów i build zakończone powodzeniem.

Publiczna kontrola po wdrożeniu przeszła bez zapisu danych użytkowników:

- frontend i `/healthz/`: HTTP 200;
- dzisiejsza plansza: pięć ról, każda z dokładnie dwoma wymaganiami;
- wyszukiwanie Fakera ze zdjęciem oraz dostęp API do PostgreSQL i Redisa: HTTP 200;
- CORS dla produkcyjnego originu i preflight dozwolone, niezaufany origin blokowany;
- przyszła plansza i jej rozwiązania: HTTP 404;
- plik CSS panelu administracyjnego z hashem w nazwie: HTTP 200.

Neon zawiera 882 tożsamości, 738 zweryfikowanych uczestników Worlds, 733 zdjęcia, 737 kompletnych statystyk kariery, 31 plansz i 310 oznaczonych składów testowych. Nie migrowano kont użytkowników.

Po kolejnych wdrożeniach powtórz:

```sh
curl --fail https://lol-kontra.onrender.com/healthz/
curl --fail https://lol-kontra.onrender.com/api/v1/dailies/today/
```

Pierwsza odpowiedź powinna zawierać `{"status":"ok"}`. Następnie otwórz frontend, sprawdź pobranie planszy i wyszukiwanie zawodnika oraz brak błędów CORS i przekierowań HTTPS. Sam healthcheck nie sprawdza gotowości usług zewnętrznych.

Szerszą procedurę migracji, kontroli danych i kopii opisuje [DEPLOYMENT.md](DEPLOYMENT.md).
