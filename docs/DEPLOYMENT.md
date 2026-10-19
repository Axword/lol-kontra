# Wdrożenie i dane

## Co jest w repozytorium

Zwykłe `python manage.py migrate --noinput` na pustym PostgreSQL instaluje schemat i zamrożony pakiet danych z 18.10.2026, a następnie stosuje aktualizacje wydania:

- 882 tożsamości zawodników, w tym 738 ze zweryfikowanymi danymi Worlds;
- statystyki (w tym 737 kompletnych statystyk kariery), historię lig i turniejów, championów oraz metadane 733 zdjęć;
- 31 plansz na październik 2026, po pięć ról i dokładnie dwa wymagania;
- zero syntetycznych rozgrywek i wyborów po zakończeniu wszystkich migracji;
- konfigurację punktacji.

Zdjęcia są adresami źródłowymi Leaguepedii; migracja nie pobiera plików zdjęć. Wymagania oparte na niekompletnych danych pozostają wyłączone. Przyszłe plansze są zapisane, ale API udostępnia je dopiero w odpowiednim dniu według `Europe/Warsaw`. Procenty wyborów, ranking i statystyki uwzględniają wyłącznie prawdziwe rozgrywki; rekordy oznaczone `is_seed` są pomijane.

Historyczna migracja październikowego wydania tworzyła oznaczone składy testowe. Pozostaje niezmieniona, a osobna migracja usuwa te rozgrywki wraz z ich odpowiedziami. Na istniejącej bazie zachowuje rozgrywki i odpowiedzi prawdziwych graczy. Nowa instalacja kończy migracje z 31 planszami i bez syntetycznych głosów.

Punktacja jest sumą zapisanych procentów poprawnych wyborów oraz 100 za każdą pustą pozycję; niższy wynik jest lepszy. Migracja scoring.0007 przelicza liczby punktów i ich statystyki, zachowując wybory, procenty, próby oraz diamenty. Kolor rzadkości wynika z dokładnego procentu: poniżej 2% złoty, od 2% do poniżej 5% epicki (fioletowy), od 5% do poniżej 15% rzadki (niebieski), od 15% do poniżej 25% niepospolity (zielony), od 25% pospolity (biały). Pierwsza prawdziwa poprawna odpowiedź dla danej pary pozycja–zawodnik na planszy otrzymuje trwałą flagę diamentu: błękitną kartę, obramowanie i mały diament, niezależnie od późniejszej popularności. Sam procent 0% nie nadaje tej flagi. Przy zawodniku wyświetlany jest sam procent; suma punktów pozostaje wynikiem całej gry.

Usunięcie syntetycznych głosów nie zmienia historycznie zdobytych punktów ani zapisanych składów prawdziwych graczy. Własny skład zachowuje procenty użyte do obliczenia jego wyniku. Aktualna popularność i liczba głosów są widoczne w liście wszystkich odpowiedzi oraz alternatywnych składach. Migracja diamentów odtwarza pierwsze prawdziwe trafienie z chronologii poprawnych prób, a przy jej braku z czasu zapisanej gry; nie zmienia punktów ani postępu.

Ukończenie kolejnej gry archiwalnej zapisuje wyłącznie wynik jej gracza. Nowa odpowiedź używa udziałów z prawdziwych wyborów sprzed tej próby; nie przelicza wcześniejszych ukończonych gier. Polecenia administracyjnego przeliczania punktów są oddzielną, jawną operacją.

Pliki wymagane w commicie:

- `backend/apps/players/fixtures/releases/worlds_players_2026_10_18_v1.json.gz`;
- `backend/apps/players/fixtures/releases/worlds_players_2026_10_19_v1.json.gz` (aktualizacja zakończonych meczów z 18 października);
- `backend/apps/dailies/fixtures/releases/october_2026_v1.json.gz`;
- wszystkie nowe migracje, w tym pomocniczy `_october_2026_release.py`;
- komendy administracyjne, konfiguracja produkcyjna i `backend/requirements.lock`.

Pakiety są sprawdzane przez SHA-256 przed zapisem. Migracje korzystają z modeli historycznych i nie wymagają połączenia z Leaguepedią. Nie zmieniaj istniejących pakietów ani zastosowanych migracji; kolejne aktualizacje danych powinny mieć nową migrację i nowy plik wydania.

## Wydanie profilu, społeczności i nowej punktacji

Zmiany z 19.10.2026 dodają migracje `players.0005`, `users.0005` i `users.0006`, `dailies.0010` oraz `scoring.0007`. `players.0005` instaluje przypiętą aktualizację Worlds bez zmiany identyfikatorów. Migracje profilu zachowują nicki, zapisują wspieraną drużynę oraz trwałą informację, czy gracz ustawił wcześniej własny nick. `dailies.0010` dodaje autora planszy i tabelę moderowanych komentarzy ze skompresowanym PNG składu. Konto aplikacji potrzebuje uprawnień do nowej tabeli i jej sekwencji; ustaw domyślne granty dla obiektów tworzonych przez właściciela migracji.

Wdrożenie wymaga kolejności: kopia danych, backend z migracjami, kontrola działającego nowego API i dopiero frontend. Starszy backend nie udostępnia komentarzy ani nowych pól profilu i używa poprzedniego kierunku punktacji. Na Renderze wcześniejszy proces może jeszcze obsługiwać żądania podczas migracji nowego procesu. Po przełączeniu wdrożenia na Live i zakończeniu starych żądań sprawdź wszystkie prawdziwe rozgrywki: poprawna odpowiedź ma `points_awarded = rarity_percent - 100`, a wynik to suma zapisanych procentów i 100 za każdą brakującą pozycję. Brak historycznego procentu kosztuje 100; historyczna plansza bez pozycji zachowuje 500.

Jeśli stary proces zapisał dawną punktację już po migracji, funkcja `recalculate_saved_scores` z `scoring.0007_sum_pick_percentages` może zostać bezpiecznie powtórzona kontem właściciela w transakcji po przełączeniu backendu. Przelicza tylko liczby punktów i statystyki; nie pobiera aktualnych udziałów, nie zmienia składów, zapisanych procentów, diamentów, prób ani postępu. Ponowne uruchomienie nie zmienia wyniku obliczeń. Nie zastępuj tej operacji `score_daily`, ponieważ jawne przeliczanie całej planszy używa innej populacji głosów.

Po wdrożeniu sprawdź `/healthz/`, katalog 19 drużyn, profil wcześniej istniejącego gościa i wznowienie jego archiwalnego składu. Kontrola komentarzy powinna potwierdzić, że osoba przed ukończeniem planszy nie otrzymuje tekstu ani adresu PNG. Nowy generator nie używa warunku debiutu od 2020 roku, ale istniejące plansze nadal go rozpoznają. Obrazy drużyn trafiają z frontendem; mapa potrzebna do generowania PNG znajduje się także w `backend/assets/rift-map.png`.

Na istniejącej bazie import zachowuje identyfikatory zawodników, plansze i postęp gry. Istniejące daty plansz nie są nadpisywane. Powtórne wdrożenie nie regeneruje kalendarza ani głosów. Nieprawidłowe stare rekordy zatrzymają migrację z informacją o problemie, bez automatycznego usuwania danych.

**Konta i rozgrywki prawdziwych użytkowników nie są eksportowane do repozytorium.** Aby przenieść także te dane z istniejącego serwera, potrzebna jest jego kopia PostgreSQL. Sama migracja odtwarza dane gry, nie prywatne zapisy użytkowników.

## Nowy serwer z Docker Compose

Poniższe polecenia wykonuj w katalogu projektu. Produkcja ma osobny projekt Compose i trwałe wolumeny. Nie łącz pliku produkcyjnego z deweloperskim `docker-compose.yml`.

```sh
cp .env.prod.example .env.prod
```

Uzupełnij `.env.prod`: losowy `DJANGO_SECRET_KEY` o długości co najmniej 50 znaków, publiczną domenę w `DJANGO_ALLOWED_HOSTS` bez protokołu oraz dwa różne konta PostgreSQL z osobnymi silnymi hasłami (minimum 16 znaków). `POSTGRES_USER` jest właścicielem używanym przy migracjach, a `POSTGRES_APP_USER` kontem aplikacji. Nie zapisuj rzeczywistych sekretów w plikach przykładowych. `.env.prod` jest ignorowany przez Git.

Ruch publiczny powinien przechodzić przez reverse proxy z HTTPS do `127.0.0.1:8080`. Proxy musi zachować publiczny nagłówek `Host` oraz nadpisać `X-Forwarded-Proto` wartością `https`. Backend ufa temu nagłówkowi w tym wariancie wdrożenia. Ustaw `HTTP_PORT`, jeśli potrzebujesz innego portu lokalnego. Przy wspólnej domenie frontendu i API listy CORS/CSRF mogą pozostać puste; dla osobnych originów podaj pełne adresy HTTPS.

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
docker compose --env-file .env.prod -f docker-compose.prod.yml logs release
```

Jednorazowa usługa `release` czeka na bazę, blokuje równoległe inicjalizacje blokadą PostgreSQL, wykonuje migracje, sprawdza komplet danych i uprawnienia aplikacji, a następnie zbiera pliki statyczne. API, worker i beat startują dopiero po jej sukcesie. Błąd nie jest ignorowany. Kontenery aplikacji korzystają z konta bez uprawnień administratora bazy i bez możliwości tworzenia tabel lub zmiany `django_migrations`.

Baza i Redis mają wyłącznie sieć wewnętrzną, bez publicznie wystawionych portów. Obrazy backendu i frontendu uruchamiają aplikację jako użytkownik bez roota. Pythonowe zależności są przypięte wraz z hashami w `requirements.lock`; obrazy i CI weryfikują hashe podczas instalacji.

Kontrola po wdrożeniu:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm release python manage.py check_release_data
```

Na świeżej, niezmienianej instalacji można dodać `--strict`, aby porównać także dane zawodników z pakietem wydania i sprawdzić brak syntetycznych rozgrywek oraz odpowiedzi. Zwykła kontrola pozwala na późniejsze aktualizacje danych źródłowych.

Jeżeli dzień dzisiejszy nie jest objęty zapisanym kalendarzem, `bootstrap_database` tworzy go tylko wtedy, gdy taka data jeszcze nie istnieje. Endpoint dzisiejszej planszy również potrafi przygotować brakujący dzień na żądanie. Nie ma automatycznego zadania Celery generującego kalendarz. Bootstrap nie nadpisuje istniejącej planszy ani nie publikuje automatycznie istniejącego szkicu.

## Kopia przed aktualizacją i przenoszenie istniejącej bazy

Przed aktualizacją działającego serwera:

```sh
# Przygotowanie prywatnego katalogu na standardowym rootful Dockerze (jednorazowo).
sudo install -d -o 0 -g 0 -m 0700 backups
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile maintenance run --rm backup
```

Kontener kopii działa jako UID 0 bez dodatkowych capabilities i musi mieć prawo zapisu do tego katalogu. Przy rootless Dockerze lub mapowaniu UID dostosuj właściciela katalogu do rzeczywistego UID procesu na hoście.

Kopia w formacie `pg_dump --format=custom` trafia do prywatnego katalogu `backups/` na hoście. Skrypt kończy się błędem przy nieudanym eksporcie i sprawdza spis archiwum przez `pg_restore --list`, zanim nada plikowi końcową nazwę. Katalog jest ignorowany przez Git. Kopie przechowuj również poza serwerem. Usługa nie wykonuje automatycznego harmonogramu ani usuwania starszych kopii.

Przy przenoszeniu rozgrywek odtwórz kopię **do osobnej, pustej bazy**, zanim wykonasz `bootstrap_database`. Użyj `pg_restore --no-owner --no-acl --exit-on-error` kontem właściciela. Nie używaj `--clean` na działającej bazie. Po odtworzeniu nadaj kontu aplikacji uprawnienia do istniejących tabel i sekwencji, a następnie uruchom nowe migracje. Właściciel musi być właścicielem odtwarzanych obiektów.

Skrypt `infra/postgres/init-runtime-role.sh` zakłada konto i domyślne uprawnienia tylko podczas pierwszego startu **pustego** wolumenu PostgreSQL. Na istniejącym wolumenie lub u dostawcy zarządzanej bazy administrator musi zapewnić odpowiadające mu konto i granty. `bootstrap_database` sprawdza połączenie, brak praw administracyjnych, dostęp do tabel i sekwencji oraz blokadę historii migracji. Nie podmieniaj hasła w samym `.env.prod`, oczekując zmiany hasła już istniejącej roli w PostgreSQL.

Nie używaj `docker compose down -v` ani poleceń czyszczących dane do aktualizacji produkcji. Migracje nie zastępują kopii zapasowej.

## Frontend na Vercelu

Projekt Vercel publikuje [jasny frontend](https://lol-kontra.vercel.app) z katalogu `frontend` i gałęzi `master`. Django API `https://lol-kontra.onrender.com/api/v1` działa na Renderze; backend `0f78ae4` osiągnął Live 19.10.2026. `NEXT_PUBLIC_API_URL` ustawiono dla Production i Preview; 18 kluczy backendu zaimportowano prywatnie do Rendera. PostgreSQL Neon i prywatny cache Redis działają. Publiczna kontrola API potwierdziła usunięcie syntetycznych głosów, profile gości oraz powrót do dawnych składów i wyników. Migracja pierwszych trafień zachowała punkty i postęp 40 wcześniejszych gier. Worker i scheduler Celery nadal nie są wdrożone; nie utworzono płatnych zasobów. Ustawienia usług, identyfikatory wdrożeń i wyniki kontroli opisuje [RENDER.md](RENDER.md).

W ustawieniach projektu Vercel wybierz:

- Root Directory: `frontend`;
- Framework Preset: Next.js;
- Production Branch: `master`;
- Install Command: `npm ci`, Build Command: `npm run build`;
- Output Directory: domyślne ustawienie Next.js, bez nadpisania na `out` lub `.next/standalone`.

Przed wdrożeniem ustaw `NEXT_PUBLIC_API_URL` w środowisku Production, a jeśli korzystasz z podglądów, również Preview. Wartością musi być publiczny adres HTTPS Django z prefiksem API, przykładowo `https://api.example.com/api/v1` — to przykład, który trzeba zastąpić własnym hostem. Adres nie może zawierać loginu, hasła, query ani fragmentu, wskazywać localhost/loopback ani domeny tego frontendu. Samo `/api/v1` jest przeznaczone dla wariantu Docker z Nginx; ten projekt Next.js nie ma proxy ani własnych endpointów Django.

Konfiguracja zatrzymuje build Vercela przy brakującym lub nieprawidłowym adresie API, zanim taki build zastąpi działającą wersję. Lokalne uruchamianie i Docker zachowują dotychczasowe adresy. `VERCEL_ENV=development` jest traktowane jako środowisko lokalne. Po zmianie adresu API wykonaj nowe wdrożenie: [Next.js zapisuje zmienne `NEXT_PUBLIC_` podczas builda](https://nextjs.org/docs/pages/guides/environment-variables#bundling-environment-variables-for-the-browser).

Na hostingu Django ustaw `DJANGO_ALLOWED_HOSTS` na rzeczywisty host API, a `CORS_ALLOWED_ORIGINS` na dokładny adres HTTPS frontendu, np. `https://projekt.vercel.app`. Przy użyciu sesji lub żądań wymagających CSRF dodaj ten origin również do `CSRF_TRUSTED_ORIGINS`. Dodatkowe domeny podglądów wymagają jawnego dopisania odpowiednich originów; produkcyjna konfiguracja nie dopuszcza wildcardów. Sekrety PostgreSQL i Django pozostają na hostingu backendu.

Test blokady konfiguracji uruchamia się przez `cd frontend && npm run test:config`; jest również częścią `npm test`. Zmienne i powiązanie Git projektu Vercel są ustawieniami hostingu — sam push nie konfiguruje API ani bazy.

## Hosting z zarządzanym PostgreSQL

Komendy można uruchamiać bez Compose. W kroku wydania użyj konta właściciela i bezpośredniego połączenia PostgreSQL:

```sh
python manage.py bootstrap_database
python manage.py collectstatic --noinput
```

Ustaw jednocześnie `POSTGRES_APP_USER` i `POSTGRES_APP_PASSWORD`, aby krok wydania zweryfikował osobną rolę aplikacji. W procesach API/Celery ustaw już jej własny `DATABASE_URL` albo `POSTGRES_USER`/`POSTGRES_PASSWORD`. Migracje i blokada sesyjna wymagają połączenia bez puli w trybie transakcyjnym. Parser `DATABASE_URL` zachowuje opcje TLS dostawcy, w tym `sslmode` i certyfikaty. Dla połączenia zewnętrznego ustaw TLS zgodnie z wymaganiami dostawcy. Konfiguracja `DEBUG=false` wymaga jawnych sekretów, hostów i danych połączenia.

## Neon

Projekt jest połączony z Neon (`hidden-math-61798935`, gałąź `production`). Kontekst CLI oraz główny `.env` są ignorowane przez Git. Szczegóły inicjalizacji i poleceń z katalogu głównego znajdują się w [NEON.md](NEON.md).

Neon zapisuje w głównym `.env` `DATABASE_URL` (pooled), `DATABASE_URL_UNPOOLED` (direct) i `NEON_BRANCH`. Zachowaj te klucze oraz pozostałe lokalne ustawienia podczas następnego `neon env pull`. API i Celery korzystają z osobnego `DATABASE_RUNTIME_URL` z ograniczoną rolą. Migracje oraz `bootstrap_database` wymagają bezpośredniego połączenia właściciela z `DATABASE_URL_UNPOOLED`; sesyjna blokada wdrożenia nie może korzystać z transaction poolera. Sekrety i wcześniejsze kopie `.env` pozostają prywatne.

`npm run build`, `npm test` i `npm run lint` można wykonywać z katalogu głównego. Delegują one do frontendu; krok migracji i uruchomienie Django/Celery wykonuje się osobno. Architektura pozostaje bez zmian: przeglądarka → Django API → PostgreSQL. Kod przeglądarki nie dostaje żadnego `DATABASE_*` ani hasła Neon.

## Weryfikacja przed commitem

```sh
cd backend
python manage.py makemigrations --check --dry-run
python -m tests.deploy_smoke
pytest -q
```

Test wdrożenia wymaga lokalnego PostgreSQL i konta z `CREATEDB`/`CREATEROLE`. Tworzy osobną losową bazę i rolę, sprawdza prawdziwe migracje od zera, ponowne wdrożenie, zachowanie postępu, ukrywanie przyszłych plansz i faktyczny brak praw DDL konta aplikacji. Usuwa tylko własną bazę i rolę testową; nie migruje bazy aplikacji.

Po podłączeniu Neon ustaw dla tego lokalnego testu `DATABASE_URL` jawnie na lokalny PostgreSQL. Główny `.env` zawiera już połączenie Neon; nie polegaj na jego domyślnych wartościach przy uruchamianiu testów administracyjnych.

Zmiany zależności zapisuj najpierw w `requirements.txt`, następnie odtwórz lock i ponownie wykonaj testy:

```sh
uv pip compile requirements.txt --universal --python-version 3.12 --generate-hashes --output-file requirements.lock
```
