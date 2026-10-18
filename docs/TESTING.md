# Testy i weryfikacja

Weryfikacja WORDS V z 19.10.2026: **458 testów backendu i 190 testów frontendu przeszło**, build również. Testy obejmują nowe progi rzadkości, trwałe pierwsze trafienie, bezpieczny backfill diamentów, zdjęcie poprawnej odpowiedzi po ponownym otwarciu gry oraz zachowanie punktów i procentów własnego składu. Wyszukiwarka nie filtruje po roli: Faker pojawia się na Topie, a błędny wybór zabiera życie i pozostawia wynik 500. Pierwsze trafienie zachowuje własne 0% na karcie i w powiadomieniu, również po odświeżeniu, zakończeniu i powrocie do archiwum, mimo bieżącej popularności 100%. Oba przypadki sprawdzono także w przeglądarce na izolowanej lokalnej bazie. Wygląd został zaakceptowany przed publikacją. Kontrola produkcyjnego backendu potwierdziła zachowanie 40 gier, 179 odpowiedzi i 245 prób, odtworzyła osiem dawnych ukończonych plansz oraz zweryfikowała 104 diamentowe pierwsze trafienia. Wcześniejsza kontrola obejmowała moderację nicków, ranking gości, prawdziwe głosy i blokadę przyszłych dat.

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
- Frontend: tożsamość gościa, odpowiedzi z wielu okien, odświeżanie daty w Warszawie, błędy sieci, warunki PL/EN, suma punktów z API, podsumowanie i rozwiązania, klawiatura oraz dialogi. Przy zawodniku wyświetlany jest sam procent: poniżej 2% złoty, od 2% do poniżej 5% fioletowy, od 5% do poniżej 15% niebieski, od 15% do poniżej 25% zielony, od 25% biały. Trwała flaga pierwszego trafienia nadaje diamentowe tło, obramowanie i mały diament; samo 0% jej nie nadaje. Zapisane zdjęcie i procent użyty do punktacji pozostają po powrocie do własnego składu; lista odpowiedzi pokazuje bieżącą liczbę głosów i udział procentowy.

## Lokalny kalendarz i kontrola UI

```sh
python manage.py prepare_month --month 2026-10
```

`prepare_month` domyślnie używa `--voters 0` i nie tworzy syntetycznych głosów. Dodatnie `--voters` muszą zakończyć się błędem. Na świeżej bazie po wszystkich migracjach oraz po przygotowaniu miesiąca oczekujemy 31 plansz, 155 pozycji i zera syntetycznych rozgrywek oraz odpowiedzi.

Weryfikacja lokalna z 18.10.2026 objęła 31 październikowych plansz i 155 pozycji. Po imporcie lig każda pozycja nadal miała dwa wymagania, 8–70 kandydatów i rozwiązanie pięcioma różnymi zawodnikami. Widocznych było wtedy 18 plansz; 13 przyszłych pozostawało ukrytych także przy bezpośrednich żądaniach API. Historyczny pakiet wydania pozostaje zamrożony; kolejne migracje zachowują ten kalendarz i usuwają dołączone kiedyś syntetyczne rozgrywki.

Przy zmianach interfejsu sprawdzamy na komputerze i telefonie: planszę, wyszukiwanie z nickiem i opcjonalnym zdjęciem, odrzucenie wyboru spełniającego tylko jeden warunek, trafienie i pomyłkę, blokady po zakończeniu, wynik, rozwiązania, archiwum, ranking oraz pomoc. Brakujące lub uszkodzone zdjęcie pozostawia sam nick.

Źródła i granice kompletności danych: [WORLDS_DATA.md](WORLDS_DATA.md).
