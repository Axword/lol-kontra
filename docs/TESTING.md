# Testy i weryfikacja

Weryfikacja bieżących zmian z 19.10.2026: **520 testów backendu i 223 testów frontendu przeszło**. Frontend obejmuje 40 testów konfiguracji oraz 183 testów Vitest w 22 plikach. Zakres obejmuje edycję nicku w górnym pasku, historię ustawienia własnego nicku, wybór drużyny Worlds 2026 w nagłówku i profilu, rozszerzone statystyki profilu, komentarze ze zdjęciem składu oraz nową punktację, w której niższy wynik jest lepszy. Końcowy build produkcyjny przeszedł, podobnie jak kontrola zgodności modeli z migracjami i kontrola systemowa Django.

Poprawka prezentacji rzadkości przypisuje kartom i wskaźnikom procentów bezpośrednie kolory z tej samej zaakceptowanej palety co CSS. Testy sprawdzają obliczone kolory tła i tekstu przy wszystkich progach, w czasie gry, podczas przeglądania wyniku oraz na liście mobilnej. Flaga historycznego diamentu nadal ma pierwszeństwo, a zwykły brak procentu nie otrzymuje wymyślonej rzadkości. Panel autora korzysta z przekazanego przez właściciela awatara 40×40; jest to na razie wspólny domyślny obraz wszystkich autorów, przy zachowaniu ich własnych nazw i adresów linków.

Rozszerzony `tests.deploy_smoke` przeszedł na świeżej, izolowanej bazie z kontem aplikacji o ograniczonych uprawnieniach. Oprócz migracji i kontroli danych sprawdza zapis nicku i drużyny, ukończenie pięciu pozycji pierwszymi wyborami 0% z końcowym wynikiem 0 oraz publikację i odczyt rzeczywistego obrazu PNG składu. Osobny test rzeczywistego lokalnego API również przeszedł. Testy nowego pakietu danych obejmują 22 mapy Worlds 2026, aktualizację dziesięciu karier i zachowanie historycznych tożsamości oraz postępu.

Końcowa kontrola wizualna nowej wersji w przeglądarce pozostaje niewykonana: narzędzie Computer Use nie mogło wiarygodnie odczytać adresu karty. Powyższe wyniki dotyczą testów i lokalnej weryfikacji API; nie potwierdzają wdrożenia nowych zmian na produkcję.

Wcześniejsze wydanie WORDS V, również zweryfikowane 19.10.2026: **458 testów backendu i 190 testów frontendu przeszło**, build również. Testy obejmowały nowe progi rzadkości, trwałe pierwsze trafienie, bezpieczny backfill diamentów, zdjęcie poprawnej odpowiedzi po ponownym otwarciu gry oraz zachowanie punktów i procentów własnego składu. Wyszukiwarka nie filtrowała po roli: Faker pojawiał się na Topie, a błędny wybór zabierał życie i pozostawiał wynik 500. Pierwsze trafienie zachowywało własne 0% na karcie i w powiadomieniu, również po odświeżeniu, zakończeniu i powrocie do archiwum, mimo bieżącej popularności 100%. Oba przypadki sprawdzono także w przeglądarce na izolowanej lokalnej bazie. Wygląd został zaakceptowany przed publikacją. Kontrola ówczesnego produkcyjnego backendu potwierdziła zachowanie 40 gier, 179 odpowiedzi i 245 prób, odtworzyła osiem dawnych ukończonych plansz oraz zweryfikowała 104 diamentowe pierwsze trafienia. Wcześniejsza kontrola obejmowała moderację nicków, ranking gości, prawdziwe głosy i blokadę przyszłych dat.

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

- Generator: dokładnie dwa niezależne warunki z różnych motywów na każdej pozycji, 8–150 kandydatów oraz rozwiązanie pięcioma różnymi zawodnikami. Nieudana generacja nie upraszcza pozycji do jednego warunku. Warunek „Debiut na Worlds od 2020 roku” nie trafia do nowych plansz, ale zachowuje walidację na istniejących planszach archiwalnych.
- Dane: granice Worlds, aliasy i tożsamości, kompletność gier, WR i progi liczby gier, TOP 5 championów z remisami, osiągnięcia, etapy odpadnięcia, zdjęcia i źródłowa historia lig. Regresje lig obejmują oficjalne aliasy OGN/SEA Tour oraz brak zastępowania metadanych rezydencją. Importy zachowują identyfikatory i inne metadane; aktualizacja historii ma test cofania zmian przy błędzie zapisu.
- Rozgrywka: walidacja obu wymagań, limit błędów, blokowanie trafionych pozycji, równoległe żądania i prywatność odpowiedzi. Drafty i przyszłe plansze są niedostępne, a rozwiązania wymagają zakończenia własnej gry.
- Punktacja i ranking: suma zapisanych procentów rzeczywistych wyborów plus 100 za każdą niewypełnioną pozycję, naliczane przez cały przebieg gry; niższy wynik jest lepszy. Pięć pozycji zaczyna od 500, pierwszy wybór 0% obniża wynik do 400, pięć wyborów 0% daje 0, a 1% + 2% + 3% + 4% + 5% daje 15. Brakujące pozycje nie otrzymują drugiej kary przy zakończeniu. Końcowy wynik jest liczbą z API; przy poszczególnych zawodnikach pozostają procenty. Regresje obejmują gry archiwalne, niższą średnią w rankingu, minimum jako najlepszy wynik, kierunek percentyla i wielokrotne administracyjne przeliczanie bez dublowania statystyk. Ukończenie kolejnej gry archiwalnej przez pojedyncze lub zbiorcze odpowiedzi zachowuje pełne rekordy wcześniejszych ukończonych gier, ich zapisane procenty, wybory i próby. Migracja zmiany punktacji przelicza wyniki z zapisanych procentów bez pobierania nowej próby głosów. Rozgrywki `is_seed` są wyłączone z procentów, rankingów i statystyk; wcześniejsza migracja usuwa wyłącznie oznaczone rozgrywki wraz z odpowiedziami, zachowując prawdziwy postęp.
- Profil i kibicowanie: niezależne aktualizacje nicku i drużyny, moderacja oraz atomowe odrzucenie błędnych zmian, trwała historia ustawienia własnego nicku, katalog 19 drużyn i ograniczenie dozwolonych identyfikatorów w bazie. Statystyki obejmują najczęściej wybieranego zawodnika i TOP 5, liczbę trafień i pomyłek, skuteczność, bezbłędne gry oraz średni zapisany procent. Prywatne, nieukończone i syntetyczne gry nie zawyżają tych danych.
- Społeczność: komentarz ze składem wymaga zakończenia własnej gry; obraz PNG powstaje z zapisanego wyniku i procentów. Ponowne wysłanie jest idempotentne, moderacja działa przed zapisem, a edycja tekstu zachowuje snapshot składu. Treść i adres obrazu pozostają ukryte przed osobą, która nie ukończyła planszy. Testy obejmują ochronę przed publikacją cudzej gry, przyszłe i nieopublikowane plansze, limity obrazu, bezpieczne pobieranie zweryfikowanych portretów oraz rankingi graczy i kibicowanych drużyn.
- Frontend: tożsamość gościa, odpowiedzi z wielu okien, odświeżanie daty w Warszawie, błędy sieci, warunki PL/EN, suma punktów z API, podsumowanie i rozwiązania, klawiatura oraz dialogi. Na kartach obok procentu wyświetlana jest nazwa rzadkości w języku interfejsu. Progi kolorów: poniżej 2% złoty, od 2% do poniżej 5% fioletowy, od 5% do poniżej 15% niebieski, od 15% do poniżej 25% zielony, od 25% biały. Trwała flaga pierwszego trafienia nadaje diamentowe tło, obramowanie i mały diament; samo 0% jej nie nadaje. Zapisane zdjęcie i procent użyty do punktacji pozostają po powrocie do własnego składu; lista odpowiedzi pokazuje bieżącą liczbę głosów i udział procentowy.

## Lokalny kalendarz i kontrola UI

```sh
python manage.py prepare_month --month 2026-10
```

`prepare_month` domyślnie używa `--voters 0` i nie tworzy syntetycznych głosów. Dodatnie `--voters` muszą zakończyć się błędem. Na świeżej bazie po wszystkich migracjach oraz po przygotowaniu miesiąca oczekujemy 31 plansz, 155 pozycji i zera syntetycznych rozgrywek oraz odpowiedzi.

Weryfikacja lokalna z 18.10.2026 objęła 31 październikowych plansz i 155 pozycji. Po imporcie lig każda pozycja nadal miała dwa wymagania, 8–70 kandydatów i rozwiązanie pięcioma różnymi zawodnikami. Widocznych było wtedy 18 plansz; 13 przyszłych pozostawało ukrytych także przy bezpośrednich żądaniach API. Historyczny pakiet wydania pozostaje zamrożony; kolejne migracje zachowują ten kalendarz i usuwają dołączone kiedyś syntetyczne rozgrywki.

Przy zmianach interfejsu sprawdzamy na komputerze i telefonie: planszę, wyszukiwanie z nickiem i opcjonalnym zdjęciem, odrzucenie wyboru spełniającego tylko jeden warunek, trafienie i pomyłkę, blokady po zakończeniu, wynik, rozwiązania, archiwum, ranking oraz pomoc. Brakujące lub uszkodzone zdjęcie pozostawia sam nick.

Źródła i granice kompletności danych: [WORLDS_DATA.md](WORLDS_DATA.md).
