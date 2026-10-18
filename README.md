# League of Legends Esports Roster Challenge — Worlds XI

Codzienna gra inspirowana Kontra.games: ułóż skład TOP / JUNGLE / MID / ADC / SUPPORT. Każdy zawodnik musi spełniać dokładnie dwa wymagania pozycji, a pięć wyborów musi dotyczyć różnych osób. Interfejs jest dostępny po polsku i angielsku.

Zaczynasz z 500 punktami. Poprawny wybór odejmuje procent osób, które wybrały tego zawodnika na tej pozycji; wyższy wynik jest lepszy. Masz 10 pomyłek. Po zakończeniu gry każde niewypełnione miejsce odejmuje 100 punktów. Gry archiwalne również liczą się do wyników i rankingów.

Stack: Next.js 14, React, TypeScript, Tailwind, Django 5.2 LTS, DRF, PostgreSQL 16, Redis 7 i Celery.

## Uruchomienie

```sh
cp .env.example .env
docker compose up --build
```

Gra: <http://localhost>, API: <http://localhost/api/v1/>, Swagger: <http://localhost/api/docs/>, panel administracyjny: <http://localhost/admin/>. Konto administratora utworzysz przez `make createsuperuser`.

Migracje instalują zamrożony pakiet 882 tożsamości z pełnymi dostępnymi metadanymi oraz 31 październikowych plansz. Ostatnia migracja usuwa oznaczone sztuczne rozgrywki i odbudowuje popularność z prawdziwych wyborów. Historyczne punkty, składy, odpowiedzi i postęp prawdziwych graczy pozostają zachowane. Nie potrzebuje dostępu do Leaguepedii. Entrypoint wykonuje `bootstrap_database`: blokadę równoległego startu, migracje i kontrolę kompletności; błąd przerywa start. Brakującą dzisiejszą planszę przygotowuje oddzielnie.

Przed publicznym hostingiem użyj oddzielnego `docker-compose.prod.yml`, prywatnego `.env.prod` i zewnętrznego HTTPS proxy. [Instrukcja wdrożenia, uprawnienia i backup](docs/DEPLOYMENT.md).

## Polecenia

```sh
make up                 # uruchom środowisko Docker
make down               # zatrzymaj środowisko
make logs               # logi usług
make migrate            # migracje bazy
make seed               # seed_players --full: aktualizacja z kanonicznego pliku
make createsuperuser
make test               # testy backendu i frontendu
```

Przygotowanie pojedynczej planszy lub kalendarza deweloperskiego:

```sh
docker compose exec api python manage.py create_daily --publish
docker compose exec api python manage.py prepare_month --month 2026-10
```

`prepare_month` tworzy plansze bez sztucznych głosów; opcja `--voters` przyjmuje tylko `0`. Stare polecenie `seed_history` jest wyłączone. Ponowne uruchomienie zachowuje istniejące odpowiedzi. Przyszłe plansze otwierają się dopiero w dniu swojej daty w strefie Europe/Warsaw; API nie ujawnia ich wcześniej.

Gość może ustawić nick w profilu. Ranking pokazuje `Gość-nick` lub wygenerowaną nazwę; zmiana nicku zachowuje tożsamość i statystyki. Nicki sprawdza serwerowy filtr. [Profil gościa i API](docs/GUEST_PROFILES.md).

## Dane i weryfikacja

Kanoniczny plik zachowuje 882 tożsamości, z czego 738 ma potwierdzone występy w 1389 grach Worlds. Dostępne są 733 zdjęcia Leaguepedii i kompletne statystyki zarejestrowanej kariery 737 osób; sprzeczne źródło JackeyLove pozostaje niekompletne.

Historia lig 738 zawodników została zweryfikowana na podstawie rzeczywistych występów i metadanych turniejów. Dla 17 osób źródło nie potwierdza konkretnej ligi regionalnej; rezydencja zawodnika nie zastępuje tego dowodu.

- [Dane, ograniczenia źródeł i odtwarzalne odświeżanie](docs/WORLDS_DATA.md).
- [Testy i aktualny zakres weryfikacji](docs/TESTING.md).

Struktura: `frontend/` — interfejs; `backend/` — API, generowanie plansz, punktacja i import danych; `infra/` — konfiguracja Nginx. Historyczny scraper znajduje się w `scraper/`; bieżący import korzysta z poleceń Django opisanych w dokumentacji danych.
