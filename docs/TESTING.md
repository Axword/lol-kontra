# Testy i weryfikacja

Weryfikacja z 19.10.2026 po usunięciu syntetycznych głosów, dodaniu profili gości i zabezpieczeniu historycznych wyników: **448 testów backendu i 167 testów frontendu przeszło**. Build frontendu oraz test świeżej instalacji i ponownej migracji zakończyły się poprawnie. Publiczna kontrola API odtworzyła osiem dawnych ukończonych plansz ze składami i zachowanymi wynikami oraz sprawdziła moderację nicków, ranking gości, prawdziwe głosy i blokadę przyszłych dat.

## Uruchomienie

Backend wymaga PostgreSQL z połączeniem ustawionym przez `DATABASE_URL` albo `POSTGRES_*`. Pytest tworzy osobną bazę `test_<nazwa_bazy>`; nie wykorzystuje rozgrywek z bazy aplikacji. `config.settings_test` ustawia cache w pamięci i wyłącza ograniczenia częstotliwości żądań na czas testów.

```sh
cd backend
pytest --ds=config.settings_test -q
python manage.py makemigrations --check --dry-run
python -m tests.deploy_smoke
```

```sh
cd frontend
npm ci
npm test
npm run lint
npm run build
```

`npm test` wykonuje jeden przebieg; `npm run test:watch` obserwuje zmiany. W działającym środowisku Docker oba zestawy uruchamia `make test`. CI sprawdza testy, zgodność migracji, lint i kompilację frontendu wraz z typami.

`tests.deploy_smoke` wymaga konta PostgreSQL z `CREATEDB` i `CREATEROLE`. Tworzy własną losową bazę oraz rolę. Sprawdza migracje od zera bez sieci, 882 tożsamości, 738 zweryfikowanych zawodników, 31 plansz oraz brak syntetycznych rozgrywek i wyborów po zakończeniu migracji. Następnie sprawdza ponowne wdrożenie bez zmiany danych ani postępu, prawidłowość wszystkich plansz, niedostępność przyszłych dat oraz rzeczywistą odmowę tworzenia tabel i modyfikowania historii migracji przez konto aplikacji. Test usuwa tylko własne zasoby.

Nowe testy obejmują ograniczenia PostgreSQL przy bezpośrednim zapisie przez ORM, wartości graniczne i NaN/Infinity, bezpieczne migracje istniejących rekordów, walidację produkcyjnych ustawień, parser połączenia z TLS oraz pakiety danych z kontrolą sum i zachowaniem istniejących plansz. Instrukcja hostingu i kopii: [DEPLOYMENT.md](DEPLOYMENT.md).

## Zakres regresji

- Generator: dokładnie dwa niezależne warunki z różnych motywów na każdej pozycji, 8–150 kandydatów oraz rozwiązanie pięcioma różnymi zawodnikami. Nieudana generacja nie upraszcza pozycji do jednego warunku.
- Dane: granice Worlds, aliasy i tożsamości, kompletność gier, WR i progi liczby gier, TOP 5 championów z remisami, osiągnięcia, etapy odpadnięcia, zdjęcia i źródłowa historia lig. Regresje lig obejmują oficjalne aliasy OGN/SEA Tour oraz brak zastępowania metadanych rezydencją. Importy zachowują identyfikatory i inne metadane; aktualizacja historii ma test cofania zmian przy błędzie zapisu.
- Rozgrywka: walidacja obu wymagań, limit błędów, blokowanie trafionych pozycji, równoległe żądania i prywatność odpowiedzi. Drafty i przyszłe plansze są niedostępne, a rozwiązania wymagają zakończenia własnej gry.
- Punktacja i ranking: 500 punktów minus procenty rzeczywistych wyborów, końcowe potrącenia za puste pozycje, gry archiwalne i wielokrotne administracyjne przeliczanie bez dublowania statystyk. Ukończenie kolejnej gry archiwalnej przez pojedyncze lub zbiorcze odpowiedzi zachowuje pełne rekordy wcześniejszych ukończonych gier, ich punktację, wybory i próby. Rozgrywki `is_seed` są wyłączone z procentów, rankingów i statystyk. Migracja usuwa wyłącznie oznaczone rozgrywki wraz z odpowiedziami, zachowując prawdziwy postęp.
- Frontend: tożsamość gościa, odpowiedzi z wielu okien, odświeżanie daty w Warszawie, błędy sieci, warunki PL/EN, suma punktów z API, podsumowanie i rozwiązania, klawiatura oraz dialogi. Przy zawodniku wyświetlany jest sam procent: poniżej 2% złoty, od 2% do poniżej 5% fioletowy, od 5% do poniżej 15% zielony, od 15% biały. Dokładne 0% ma mały diament, a dodatni procent zaokrąglony do małej wartości nie może dostać oznaczenia 0%.

## Lokalny kalendarz i kontrola UI

```sh
python manage.py prepare_month --month 2026-10
```

`prepare_month` domyślnie używa `--voters 0` i nie tworzy syntetycznych głosów. Dodatnie `--voters` muszą zakończyć się błędem. Na świeżej bazie po wszystkich migracjach oraz po przygotowaniu miesiąca oczekujemy 31 plansz, 155 pozycji i zera syntetycznych rozgrywek oraz odpowiedzi.

Weryfikacja lokalna z 18.10.2026 objęła 31 październikowych plansz i 155 pozycji. Po imporcie lig każda pozycja nadal miała dwa wymagania, 8–70 kandydatów i rozwiązanie pięcioma różnymi zawodnikami. Widocznych było wtedy 18 plansz; 13 przyszłych pozostawało ukrytych także przy bezpośrednich żądaniach API. Historyczny pakiet wydania pozostaje zamrożony; kolejne migracje zachowują ten kalendarz i usuwają dołączone kiedyś syntetyczne rozgrywki.

Przy zmianach interfejsu sprawdzamy na komputerze i telefonie: planszę, wyszukiwanie z nickiem i opcjonalnym zdjęciem, odrzucenie wyboru spełniającego tylko jeden warunek, trafienie i pomyłkę, blokady po zakończeniu, wynik, rozwiązania, archiwum, ranking oraz pomoc. Brakujące lub uszkodzone zdjęcie pozostawia sam nick.

Źródła i granice kompletności danych: [WORLDS_DATA.md](WORLDS_DATA.md).
