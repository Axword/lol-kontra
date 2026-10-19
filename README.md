# League of Legends Esports Roster Challenge — WORDS V

Codzienna gra inspirowana Kontra.games: ułóż skład TOP / JUNGLE / MID / ADC / SUPPORT. Każdy zawodnik musi spełniać dokładnie dwa wymagania pozycji, a pięć wyborów musi dotyczyć różnych osób. Interfejs jest dostępny po polsku i angielsku.

Zaczynasz z 500 punktami: każda z pięciu pustych pozycji kosztuje 100. Poprawna odpowiedź zastępuje ten koszt zapisanym procentem popularności zawodnika. Po uzupełnieniu składu wynik to suma pięciu procentów; **mniej punktów oznacza lepszy wynik**, a pięć pierwszych trafień po 0% daje 0 punktów. Niewypełniona pozycja zachowuje koszt 100, więc pomijanie odpowiedzi nie poprawia wyniku. Masz 10 pomyłek. Gry archiwalne również liczą się do wyników i rankingów.

Nick można zmienić bezpośrednio w nagłówku. Obok niego lub w profilu wybierzesz badge drużyny Worlds 2026, której kibicujesz. Profil pokazuje skuteczność, serie dni, diamenty i najczęściej wybieranych zawodników. Po zakończeniu gry można opublikować moderowany komentarz z automatycznym obrazem własnego składu; treść i obraz są ukryte przed osobami, które jeszcze nie skończyły tej planszy. Pole „Zapisz jako…” zapisuje wyłącznie nick i pojawia się tylko przed pierwszym ustawieniem własnego nicku.

Osobna strona rankingu pokazuje domyślnie 50 osób; dostępne limity to 10, 25, 50 i 100. Na końcu listy zawsze pojawia się dodatkowy wiersz bieżącego gracza z jego rzeczywistą pozycją, także poza pierwszą setką. Gracz bez ukończonej oficjalnej gry widzi kreskę zamiast wymyślonej pozycji. Ranking przy planszy pozostaje bez zmian.

Nowe warunki „Urodzony w Europie” i „Urodzony w Ameryce Północnej” korzystają z kraju urodzenia zapisanego przez Leaguepedię. Narodowość i historia lig nie zastępują tej informacji. Istniejące plansze zachowują dotychczasowe wymagania; dawne ogólne etykiety kontynentu są doprecyzowane jako narodowość.

Stack: Next.js 14, React, TypeScript, Tailwind, Django 5.2 LTS, DRF, PostgreSQL 16, Redis 7 i Celery.

## Uruchomienie

```sh
cp .env.example .env
docker compose up --build
```

Gra: <http://localhost>, API: <http://localhost/api/v1/>, Swagger: <http://localhost/api/docs/>, panel administracyjny: <http://localhost/admin/>. Konto administratora utworzysz przez `make createsuperuser`.

Migracje instalują zamrożony pakiet 882 tożsamości z pełnymi dostępnymi metadanymi oraz 31 październikowych plansz. Usuwają oznaczone sztuczne rozgrywki, odbudowują popularność z prawdziwych wyborów i odtwarzają trwałe wyróżnienie pierwszych trafień. Historyczne punkty, składy, odpowiedzi i postęp prawdziwych graczy pozostają zachowane. Nie potrzebują dostępu do Leaguepedii. Entrypoint wykonuje `bootstrap_database`: blokadę równoległego startu, migracje i kontrolę kompletności; błąd przerywa start. Brakującą dzisiejszą planszę przygotowuje oddzielnie.

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
