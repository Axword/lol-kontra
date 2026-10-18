# Testy i weryfikacja

Pełny przebieg z 18.10.2026 po zabezpieczeniach bazy i aktualizacji do Django 5.2.18: **371 testów backendu przeszło**. Po końcowym uszczelnieniu roli aplikacji przeszedł zestaw **83 testów konfiguracji i uprawnień**, zawierający 10 nowych regresji. Wcześniejszy przebieg frontendu: **79 testów**, kontrola typów, lint bez ostrzeżeń i kompilacja produkcyjna. Zmiany zabezpieczeń nie modyfikują UI.

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

`tests.deploy_smoke` wymaga konta PostgreSQL z `CREATEDB` i `CREATEROLE`. Tworzy własną losową bazę oraz rolę. Sprawdza migracje od zera bez sieci, 882 tożsamości, 738 zweryfikowanych zawodników, 31 plansz, 310 składów testowych i 1550 wyborów. Następnie sprawdza ponowne wdrożenie bez zmiany danych ani postępu, prawidłowość wszystkich plansz, niedostępność przyszłych dat oraz rzeczywistą odmowę tworzenia tabel i modyfikowania historii migracji przez konto aplikacji. Test usuwa tylko własne zasoby. Przeszedł również na Django 5.2.18.

Nowe testy obejmują ograniczenia PostgreSQL przy bezpośrednim zapisie przez ORM, wartości graniczne i NaN/Infinity, bezpieczne migracje istniejących rekordów, walidację produkcyjnych ustawień, parser połączenia z TLS oraz pakiety danych z kontrolą sum i zachowaniem istniejących plansz. Instrukcja hostingu i kopii: [DEPLOYMENT.md](DEPLOYMENT.md).

## Zakres regresji

- Generator: dokładnie dwa niezależne warunki z różnych motywów na każdej pozycji, 8–150 kandydatów oraz rozwiązanie pięcioma różnymi zawodnikami. Nieudana generacja nie upraszcza pozycji do jednego warunku.
- Dane: granice Worlds, aliasy i tożsamości, kompletność gier, WR i progi liczby gier, TOP 5 championów z remisami, osiągnięcia, etapy odpadnięcia, zdjęcia i źródłowa historia lig. Regresje lig obejmują oficjalne aliasy OGN/SEA Tour oraz brak zastępowania metadanych rezydencją. Importy zachowują identyfikatory i inne metadane; aktualizacja historii ma test cofania zmian przy błędzie zapisu.
- Rozgrywka: walidacja obu wymagań, limit błędów, blokowanie trafionych pozycji, równoległe żądania i prywatność odpowiedzi. Drafty i przyszłe plansze są niedostępne, a rozwiązania wymagają zakończenia własnej gry.
- Punktacja i ranking: 500 punktów minus procenty wyborów, końcowe potrącenia za puste pozycje, gry archiwalne i wielokrotne przeliczanie bez dublowania statystyk. Składy `is_seed` wpływają na procenty, ale są wyłączone z rankingów i statystyk użytkowników.
- Frontend: tożsamość gościa, odpowiedzi z wielu okien, odświeżanie daty w Warszawie, błędy sieci, warunki PL/EN, wartości punktów z API, podsumowanie i rozwiązania, klawiatura oraz dialogi.

## Lokalny kalendarz i kontrola UI

```sh
python manage.py prepare_month --month 2026-10 --voters 10
```

Weryfikacja lokalna z 18.10.2026 objęła 31 październikowych plansz, 155 pozycji i 310 oznaczonych składów testowych, czyli 1550 poprawnych wyborów. Po imporcie lig każda pozycja nadal miała dwa wymagania, 8–70 kandydatów i rozwiązanie pięcioma różnymi zawodnikami. Żadna odpowiedź prawdziwego gracza nie straciła poprawności; skorygowano 14 odpowiedzi syntetycznych składów testowych. Widocznych było 18 plansz; 13 przyszłych pozostawało ukrytych także przy bezpośrednich żądaniach API. Ten kalendarz i oznaczone składy są teraz również odtwarzane przez migrację wydania na pustej bazie.

Przy zmianach interfejsu sprawdzamy na komputerze i telefonie: planszę, wyszukiwanie z nickiem i opcjonalnym zdjęciem, odrzucenie wyboru spełniającego tylko jeden warunek, trafienie i pomyłkę, blokady po zakończeniu, wynik, rozwiązania, archiwum, ranking oraz pomoc. Brakujące lub uszkodzone zdjęcie pozostawia sam nick.

Źródła i granice kompletności danych: [WORLDS_DATA.md](WORLDS_DATA.md).
