# Testy i weryfikacja

Przegląd opisów z 20.10.2026 doprecyzowuje edycje Worlds, progi liczbowe, etapy
turnieju, play-in, TOP 5 według liczby gier i historyczne nazwy lig/drużyn.
Migracja 0018 na lokalnym kalendarzu poprawiła 168 etykiet; porównanie reguł,
identyfikatorów, gier, odpowiedzi i prób potwierdziło brak innych zmian.
Testy sprawdzają również ochronę własnych tłumaczeń autora i obsługiwane granice
roku w edytorze. Ramki wszystkich sześciu rzadkości zweryfikowano na rzeczywistych
komponentach przy szerokości komputera i 390 px: kolory i grubość są spójne,
diament zachowuje pierwszeństwo, a strona mobilna nie ma poziomego przepełnienia.

Wydanie WORLDS KONTRA z 20.10.2026: pełne kontrole GitHub CI dla backendu,
frontendu i infrastruktury przeszły na commicie `9e6c210`. Obejmują migracje od
zera, powtórne wdrożenie bez zmiany postępu, odtworzenie kopii na osobnej bazie,
przetrwanie wymiany wolumenu PostgreSQL oraz ograniczenia konta aplikacji.
Nowe standardowe plansze przechodzą minimum 10 odpowiedzi na pozycję; archiwalne
reguły zachowują dotychczasową treść i są sprawdzane pod kątem grywalności.

W przeglądarce sprawdzono grę, edytor z podglądem kandydatów, stronicowany ranking
ważony oraz przeciąganą listę wyzwań. Końcowa kontrola produkcji potwierdziła
ciemniejsze ukończone kafelki ze znacznikiem, bez numerów plansz i opisów statusu.
Przejście ze starego Vercela zachowało profil właściciela, drużynę T1 i wyniki
dwóch gier. Kontrola przed i po publikacji porównała skróty profili, odpowiedzi,
prób, komentarzy oraz rzeczywistych bajtów obrazów PNG.

Konto redaktora Axword ma tylko uprawnienia dotyczące plansz. Sprawdzono dostęp
do edytora oraz standardowego formularza zmiany własnego hasła Django Admin.
Test klucza wdrożeniowego potwierdza odmowę wykonywania dowolnych komend SSH;
oddzielne testy odrzucają wstrzyknięcie poleceń, flagi i niepełne identyfikatory.

Weryfikacja bieżących zmian z 19.10.2026: **563 różne testy backendu i 237 testów frontendu przeszło**. Pełny przebieg backendu obejmował 562 testy; po dopracowaniu blokad migracji przeszedł dodatkowo zestaw 22 testów, w tym jeden nowy test współbieżności. Frontend obejmuje 40 testów konfiguracji oraz 197 testów Vitest w 24 plikach. Zakres obejmuje edycję nicku w górnym pasku, historię ustawienia własnego nicku, wybór drużyny Worlds 2026 w nagłówku i profilu, rozszerzone statystyki profilu, komentarze ze zdjęciem składu oraz nową punktację, w której niższy wynik jest lepszy. Końcowy build produkcyjny przeszedł, podobnie jak kontrola zgodności modeli z migracjami i kontrola systemowa Django.

Osobna strona rankingu ma domyślny limit 50 oraz wybór 10/25/50/100. Dodatkowy wiersz własnego gracza jest wyświetlany także wtedy, gdy gracz znajduje się już w głównej liście. Testy sprawdzają rzeczywistą pozycję 116 przy limicie 10 i pozycję 121 dla zalogowanego użytkownika, identyczne nicki różnych osób, stabilne remisy, brak ukończonych gier oraz wykluczenie rozgrywek syntetycznych, treningowych i przyszłych. Odczyt własnej pozycji nie tworzy profilu ani rozgrywki; identyfikator gościa trafia wyłącznie do treści żądania, a odpowiedź ma zakaz współdzielonego cache. Zmiana limitu nie wyświetla przejściowo danych poprzedniej osoby ani poprzedniego limitu. Ranking planszy obok komentarzy zachowuje dotychczasowe działanie.

Regresje geograficzne odróżniają kontynent urodzenia od narodowości i ligi. Nowy `birth_continent` korzysta wyłącznie z rozpoznanego kraju urodzenia, a brak lub błędna wartość nie otrzymuje zastępczej odpowiedzi z narodowości. Istniejący `continent` zachowuje dotychczasową walidację; migracja doprecyzowuje wyłącznie znane automatyczne etykiety, zachowując niestandardowe opisy i historię gry.

Regresje ról kariery obejmują Kikisa na Topie z wymaganiami Fnatic i mniej niż 50 gier Worlds, twarde odrzucenie Fakera na Topie, zachowanie statystyk Worlds oraz trwałość dodatkowych ról po pełnym seedzie i odświeżeniu. Wszystkie 291 tożsamości i 433 dodatki w przypiętym pakiecie mają zgodne dowody; oficjalne jednorazowe występy Yellowstara na Topie nadal są poprawne. Powtórzenie wcześniejszego błędnego wyboru po poprawieniu danych może dać trafienie w aktywnej grze, także jeśli ostatnia błędna karta dotyczyła innego zawodnika. Dawne próby, licznik błędów i zapisane procenty innych trafień pozostają zachowane; gry zakończone nadal odrzucają nowe trafienia. Test dwóch niezależnych sesji PostgreSQL potwierdza możliwość zatwierdzenia nowej próby z kluczem obcym do zawodnika, gdy migracja nadal trzyma jego blokadę `FOR NO KEY UPDATE`.

Integracja Vercel Analytics przeszła `npm ci --ignore-scripts` w świeżej kopii źródeł, wszystkie testy frontendu i produkcyjny build z `VERCEL=1` oraz publicznym adresem API. Instalacja nie wymagała `--legacy-peer-deps` ani `--force`. Opublikowana wersja wymaga osobnej kontroli skryptu `/_vercel/insights/script.js` i zwykłej wizyty w przeglądarce; testy lokalne nie potwierdzają samodzielnie zbierania danych na Vercelu.

Poprawka prezentacji rzadkości przypisuje kartom i wskaźnikom procentów bezpośrednie kolory z tej samej zaakceptowanej palety co CSS. Testy sprawdzają obliczone kolory tła i tekstu przy wszystkich progach, w czasie gry, podczas przeglądania wyniku oraz na liście mobilnej. Flaga historycznego diamentu nadal ma pierwszeństwo, a zwykły brak procentu nie otrzymuje wymyślonej rzadkości. Panel autora korzysta z przekazanego przez właściciela awatara 40×40; jest to na razie wspólny domyślny obraz wszystkich autorów, przy zachowaniu ich własnych nazw i adresów linków.

Rozszerzony `tests.deploy_smoke` przeszedł na świeżej, izolowanej bazie z kontem aplikacji o ograniczonych uprawnieniach. Oprócz migracji i kontroli danych sprawdza zapis nicku i drużyny, ukończenie pięciu pozycji pierwszymi wyborami 0% z końcowym wynikiem 0 oraz publikację i odczyt rzeczywistego obrazu PNG składu. Osobny test rzeczywistego lokalnego API również przeszedł. Testy nowego pakietu danych obejmują 22 mapy Worlds 2026, aktualizację dziesięciu karier i zachowanie historycznych tożsamości oraz postępu.

Końcowa kontrola wizualna tej partii zmian w przeglądarce pozostaje niewykonana: narzędzie Computer Use nie mogło wiarygodnie odczytać adresu karty. Powyższe wyniki dotyczą testów i lokalnej weryfikacji API. Kontrola wdrożenia wymaga oddzielnego sprawdzenia produkcyjnego API, migracji i opublikowanych plików frontendu.

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

Język interfejsu wybiera pierwsza preferencja przeglądarki: `pl` i `pl-*` oznaczają polski, pozostałe języki angielski. PL/EN wybrane ręcznie pozostaje po odświeżeniu i zmianie języka urządzenia. Starszy zapis domyślnego PL przechodzi na wykrywanie automatyczne, starszy EN zachowuje ręczny wybór. Aktualizacja preferencji nie zmienia identyfikatora gościa, wyników ani ustawień pomocy. Testy obejmują również walidację nicku i komentarza, przywracanie profilu oraz generowane prefiksy nazw w rankingach. Angielski jest początkowym językiem renderowania, żeby nowy zagraniczny gracz nie otrzymywał najpierw polskiego ekranu.

Obrazki składów mają osobne adresy `?v=2&lang=pl` oraz `?v=2&lang=en`. Tłumaczenie zmienia wyłącznie nagłówek i markę; piksele wyniku oraz składu, oryginalny snapshot w bazie i adres bez parametrów pozostają niezmienione. Komentarze i własne nicki graczy zachowują oryginalną treść.

```sh
python manage.py prepare_month --month 2026-10
```

`prepare_month` domyślnie używa `--voters 0` i nie tworzy syntetycznych głosów. Dodatnie `--voters` muszą zakończyć się błędem. Na świeżej bazie po wszystkich migracjach oraz po przygotowaniu miesiąca oczekujemy 31 plansz, 155 pozycji i zera syntetycznych rozgrywek oraz odpowiedzi.

Weryfikacja lokalna z 18.10.2026 objęła 31 październikowych plansz i 155 pozycji. Po imporcie lig każda pozycja nadal miała dwa wymagania, 8–70 kandydatów i rozwiązanie pięcioma różnymi zawodnikami. Widocznych było wtedy 18 plansz; 13 przyszłych pozostawało ukrytych także przy bezpośrednich żądaniach API. Historyczny pakiet wydania pozostaje zamrożony; kolejne migracje zachowują ten kalendarz i usuwają dołączone kiedyś syntetyczne rozgrywki.

Przy zmianach interfejsu sprawdzamy na komputerze i telefonie: planszę, wyszukiwanie z nickiem i opcjonalnym zdjęciem, odrzucenie wyboru spełniającego tylko jeden warunek, trafienie i pomyłkę, blokady po zakończeniu, wynik, rozwiązania, archiwum, ranking oraz pomoc. Brakujące lub uszkodzone zdjęcie pozostawia sam nick.

Źródła i granice kompletności danych: [WORLDS_DATA.md](WORLDS_DATA.md).

## Infinity i większości ról

Regresje `test_majority_roles.py` sprawdzają rzeczywiste większości Kikisa, Yellowstara, Perkza, Ambitiona i Rekklesa, odrzucenie pojedynczych map oraz rozdzielenie Worlds od lig krajowych. Test archiwum zachowuje starą poprawną odpowiedź, jednocześnie odrzucając ten sam wybór nowego gracza według aktualnej zasady.

`test_board_factory.py` sprawdza wiele losowań na rzeczywistych danych: trzy pola Worlds, dwa inne, co najmniej dziesięć odpowiedzi po weryfikacji roli i wspólną drużynę/edycję z pięcioma różnymi pasującymi zawodnikami. Nie dopuszcza TOP 5 kariery; TOP 5 Worlds pojawia się najwyżej raz i jedynie w części zestawów. `test_worlds_editorial_release.py` kontroluje pakiet przyszłych plansz, identyfikatory pozycji, zachowanie autorskiej planszy oraz pominięcie rozpoczętych gier wraz z ich odpowiedziami i próbami.

Testy Infinity obejmują wspólne dziesięć pomyłek, przejście do kolejnej piątki, wznowienie i restart po zakończeniu, odrzucanie cudzej serii i starej planszy, ponawianie żądań, dwa równoległe trafienia, ograniczenia bazy oraz ranking jednej najlepszej serii na profil z paginacją. Frontend sprawdza PL/EN, ręczne rozpoczęcie, liczniki z API, zamknięcie starej wyszukiwarki po zmianie planszy i ochronę przed zapisaniem spóźnionej odpowiedzi do innego profilu. Lokalny test przeglądarkowy przechodzi pomyłkę, pięć trafień, nową planszę z zachowanymi życiami, odświeżenie i ranking.
