# Dane zawodników i Worlds

Stan danych Worlds: **19.10.2026, 07:18:52 UTC**. Potwierdzono 738 zawodników i 1392 fizycznie rozegranych gier w 26 eventach Worlds 2011–2026, obejmujących Main Event i Play-In. Worlds 2026 obejmuje 22 rozegrane mapy Play-In, do ostatniej mapy KC–MVK z 18 października, 19:48 UTC. IEM, IeSF, regionalne kwalifikacje i Worlds Qualifying Series są poza tym zakresem.

Kanoniczny plik `backend/apps/players/fixtures/worlds_players_full.json` zachowuje 882 tożsamości. 144 wcześniejsze rekordy bez występu w tym zakresie mają `worlds_verified=false` i są wyłączone z wyszukiwania oraz poprawnych odpowiedzi. Aktualizacje zachowują identyfikatory i istniejące rozgrywki.

| Zakres | Potwierdzony stan |
| --- | --- |
| Statystyki Worlds | 738 kompletnych zestawów do daty snapshotu |
| Osiągnięcia Worlds | 738 odświeżonych historii; pola mają własną kompletność |
| Etapy odpadnięcia | 713 kompletnych historii, 25 częściowych |
| Zdjęcia Leaguepedii | 733 dostępne, 5 potwierdzonych braków |
| Statystyki zarejestrowanej kariery | 737 kompletnych zestawów; JackeyLove niekompletny z powodu konfliktu źródła |
| Historia lig | 738 zweryfikowanych historii; dla 17 osób brak dowodu konkretnej ligi regionalnej |

## Źródła i kontrola poprawności

Publiczny [Special:CargoExport Leaguepedii](https://lol.fandom.com/wiki/Special:CargoExport) dostarcza gry, aliasy, zawodników, terminarze i placementy. Pobieranie sprawdza liczby wierszy i paginację, zapisuje zapytania i SHA-256 oraz zachowuje odstęp między żądaniami. Nie korzysta z ograniczanego anonimowego `cargoquery`.

Niezależny `MatchSchedule` potwierdza liczbę gier i wyniki serii. Każda gra musi mieć dziesięciu różnych zawodników, dwie pięcioosobowe drużyny i pięciu zwycięzców. Brak eventu, gry, sprzeczne aliasy lub wyniki blokują potwierdzenie kompletności. Tożsamość pochodzi z kanonicznej strony Leaguepedii i jej aliasów: normalizacja uwzględnia wielkość liter, HTML, Unicode oraz spacje/underscore i zachowuje rozróżnienia osób w nawiasach.

- Cargo pomija 15 ćwierćfinałowych gier 2023. Uzupełnienie 150 wpisów pochodzi z [oficjalnych scoreboardów, rewizja 4538145](https://lol.fandom.com/wiki/2023_Season_World_Championship/Main_Event/Scoreboards/Quarterfinals?oldid=4538145), połączonych RPGID z terminarzem, rewizja 4538136. Zgodne gry obecne już w Cargo nie są dodawane ponownie; konflikt zatrzymuje import.
- Cztery punkty carry-over z 2011 nie były rozegranymi grami. `MatchScheduleGame.FF` i [reguły turnieju, rewizja 4492166](https://lol.fandom.com/wiki/Season_1_World_Championship?oldid=4492166) potwierdzają 28 fizycznych gier.
- Zdjęcie pochodzi z `Players.Image` lub wpisu profilowego `PlayerImages` według reguł infoboksu. MediaWiki `imageinfo` zwraca rzeczywisty adres miniatury 128 px i metadane pliku oraz rewizji. Adresy nie są zgadywane; błąd pobierania nie jest traktowany jako potwierdzony brak i nie usuwa poprzedniego zdjęcia.

Odtwarzalne źródła w `backend/apps/players/fixtures/`:

- `worlds_source_snapshot.json.gz` — gry, aliasy, metadane, terminarz i dowody historyczne Worlds;
- `worlds_scoreboard_supplements.json` — ćwierćfinały 2023 z rewizjami;
- `worlds_eliminations_source.json.gz` — 218 oficjalnych placementów, m.in. dla eliminacji w Play-In;
- `leaguepedia_career_snapshot.json.gz` — agregaty kariery, zapytania i konflikt źródłowy;
- `leaguepedia_career_refresh_2026_10_19.json.gz` — osobny, świeży eksport kariery dziesięciu zawodników KC–MVK z niezależnymi sumami i 375 grupami championów;
- `worlds_playin_rules_source.json` — oficjalna reguła jednego awansu z czteroosobowej drabinki BO5 double-elimination oraz SHA-256 pobranej strony Riot Games;
- `leaguepedia_leagues_snapshot.json.gz` — występy w ligach, katalog lig i oficjalne przekierowania nazw.

[worlds-data-audit.json](worlds-data-audit.json) opisuje bieżący import Worlds. [Raport aktualizacji 19 października](worlds-data-refresh-2026-10-19.json) potwierdza zachowanie wszystkich 13890 wcześniejszych wierszy scoreboardów i 882 tożsamości oraz dokładnie trzy nowe mapy, 30 występów i dziesięć odświeżonych karier. Osobne raporty poleceń opisują późniejsze odświeżenia historii, zdjęć i kariery.

## Znaczenie warunków i granice kompletności

`career_stats.worlds` obejmuje wyłącznie wskazany zakres Worlds. WR i liczba gier wymagają kompletnych, spójnych sum oraz podziału po championach. Porównania `>` i `<` są ścisłe: dokładnie 50% nie spełnia `WR > 50` ani `WR < 50`, a dokładnie X gier nie spełnia żadnej strony progu X. Liczymy pojedyncze gry, nie serie BO3/BO5.

TOP 5 obejmuje championów najczęściej granych w danym zakresie i wszystkich remisujących na piątym miejscu. `worlds_top5_champion` korzysta z Worlds; `career_top5_champion` z `career_stats.career`. `Players.FavChamps`, zapisane jako `favorite_champions`, oznacza ulubione postacie i nie potwierdza TOP 5.

Zakres kariery `leaguepedia_career` oznacza wszystkie zarejestrowane scoreboardy Leaguepedii, również pokazowe i All-Star; nie gwarantuje archiwum każdej profesjonalnej gry. Uwzględnia istniejące wpisy bez daty, bez wymyślania dat. Bazowy snapshot kariery pochodzi z **18.10.2026, 10:41:05 UTC**; dziesięć osób grających w ostatnim KC–MVK ma niezależnie odświeżone sumy i championy do **19.10.2026, 07:18:52 UTC**. Pozostali zachowują datę i pochodzenie poprzedniego eksportu. Każdy z dziesięciu zawodników ma dokładnie trzy nowe gry: KC trzy zwycięstwa, MVK trzy porażki. JackeyLove ma sprzeczne wpisy dla tego samego GameId w [LPL All-Star 2023](https://lol.fandom.com/wiki/LPL_All-Star_2023/Scoreboards): różne championy i wyniki. Jego `complete=false` blokuje warunki kariery.

Historia `attributes.leagues` pochodzi z datowanych gier `ScoreboardPlayers`, połączonych przez kanoniczne aliasy z `Tournaments.League` i oficjalnym katalogiem `Leagues`. Snapshot do **18.10.2026, 09:46:04 UTC** obejmuje 321257 występów zawodników w grach, 6085 grup zawodnik–liga i 64 zapisy zapytań. Jawna mapa rodzin lig łączy historyczne nazwy; OGN→LCK i SEA Tour→LST mają dodatkowo potwierdzenie w oficjalnych przekierowaniach MediaWiki. Nie wyprowadzamy ligi z regionu drużyny, rezydencji ani samego udziału w Worlds/MSI.

Od 20.10.2026 zamianę roli zaliczamy po co najmniej jednym turnieju Worlds albo głównej ligi LEC/EU LCS, LPL, LCK/OGN lub NA (LCS/NA LCS/LTA North), w którym zawodnik rozegrał na tej pozycji ponad połowę wszystkich map swojej drużyny. Obie role muszą mieć takie potwierdzenie; pojedynczy występ i turnieje ERL nie wystarczają. Main Event i Play-In tej samej edycji Worlds tworzą jeden turniej. Mianownikiem jest liczba map drużyny, więc jedna mapa rezerwowego nie daje mu 100%. Ta zasada dotyczy nowych odpowiedzi również w archiwum. Wcześniejsze zaliczone odpowiedzi i wyniki pozostają zapisane.

Nowy pakiet `releases/majority_roles_2026_10_20_v1.json.gz` zawiera przypięte sumą SHA-256 dowody kwalifikujących większości: turniej, drużynę, rolę, liczbę map zawodnika oraz niezależnie pobraną liczbę map drużyny. Obejmuje Worlds do 19.10.2026, 07:18:52 UTC oraz osobny eksport głównych lig dla potencjalnych zamian ról; pod nową zasadę kwalifikuje się 70 dodatkowych przypisań. Kikis kwalifikuje Top/Jungle, Yellowstar ADC/Support, Perkz Mid/ADC, Ambition Mid/Jungle. Rekkles kwalifikuje Support również dzięki większości w LEC 2026 Versus dla Los Ratones. Kikis nie kwalifikuje Mid/Support, Yellowstar Top, a Faker Top. Warunek kilku ról na samych Worlds uwzględnia wyłącznie większości osiągnięte na Worlds.

Historyczny dodatek `releases/career_roles_2026_10_19_v1.json` i migracja `players.0006_verified_career_roles` pozostają niezmienione dla odtwarzalności importu. Walidator zawęża ich role według nowego pakietu większości. Samo miejsce w wierszu scoreboardu nie wystarcza: zgodnie z [deklaracją pól Leaguepedii](https://lol.fandom.com/wiki/Module:CargoDeclare/ScoreboardPlayers) i [modułem scoreboardu](https://lol.fandom.com/wiki/Module:ScoreboardAbstract) `IngameRole` opisuje rzeczywistą pozycję, a `Role` służy jako zastępstwo przy braku tej informacji. Nie wnioskujemy roli z championa. Mecze pokazowe, All-Star, turnieje streamerów, kwalifikacje i promocje nie kwalifikują większości.

Import zastąpił 525 dawnych list; dodatkowe potwierdzenie SEA Tour uzupełniło LST u Niksara i WarL0cK. Dla 17 osób, m.in. Beana i zawodników sprzed powstania lig, źródło nie potwierdza ligi regionalnej. Nie jest to twierdzenie, że nigdy w żadnej nie grali. Brak daty, nieznana etykieta turnieju lub nieprzypisane zawody nie są zamieniane na zgadywaną ligę. Przy obecności `leagues_meta` walidator nie używa `Player.residency` jako zastępstwa; niepoprawne lub niekompletne metadane nie potwierdzają warunku.

Tytuł zdobyty z drużyną i faktycznie rozegrany finał to osobne fakty: Duke ma tytuły 2016 i 2018, ale zagrał w finale tylko w 2016. Wyjście z grupy wymaga udziału drużyny w grupie lub Swiss; bye do ćwierćfinału nie wystarcza. Awans z Play-In wymaga udziału zawodnika i awansu tej samej drużyny do Main Event; samo wystąpienie jest zapisane oddzielnie. Zanim drużyna rozegra pierwszą mapę Swiss, awans może potwierdzić kompletna drabinka, datowane końcowe placementy wszystkich pozostałych uczestników i przypięte [oficjalne reguły Riot Games](https://lolesports.com/en-US/tournament/115660540725177488/overview). W 2026 potwierdza to awans Karmine Corp.

`worlds_eliminations` przechowuje lata odpadnięcia w `play_in`, `group` (grupy lub Swiss), `quarterfinal`, `semifinal` i `final`. Wynik dotyczy wszystkich, którzy zagrali w tym roku dla danej drużyny. Pojedyncza porażka w Play-In nie dowodzi eliminacji: wymagane są zakończone rozgrywki, brak drużyny w Main Event i oficjalny placement. Zakończony i w pełni potwierdzony Play-In 2026 pozwala już zapisać eliminację MVK, FURIA i Cloud9 bez czekania na finał całych Worlds. Późniejszy wynik KC oraz drabinka double-elimination czterech zespołów z 2011 pozostają częściowo nieznane. Potwierdzone dodatnie fakty pozostają dostępne przy niepełnej reszcie historii.

W polach osiągnięć brak pola oznacza nieznany wynik; pusta lista oznacza potwierdzony brak przy wystarczającym pokryciu historii. Kompletne statystyki do chwili snapshotu nie oznaczają zakończenia turnieju 2026. Historii trenerów i brakujących danych osobowych nie uzupełniamy przypuszczeniami. `NationalityPrimary`, gdy dostępne, ma pierwszeństwo przed krajem urodzenia `Country`; szeroki region rezydencji nie jest zamieniany na konkretną ligę.

## Polecenia odświeżania

Uruchamiaj z katalogu `backend` po skonfigurowaniu połączenia z bazą.

```sh
# Import kanonicznego pliku, bez kasowania tożsamości.
python manage.py seed_players --full

# Sprawdzenie i odtworzenie importu Worlds z zapisanego źródła.
python manage.py refresh_leaguepedia --snapshot apps/players/fixtures/worlds_source_snapshot.json.gz --dry-run
python manage.py refresh_leaguepedia --snapshot apps/players/fixtures/worlds_source_snapshot.json.gz --apply

# Pobranie nowego źródła Worlds i zapis snapshotu.
python manage.py refresh_leaguepedia --cache-dir ../tmp/leaguepedia-cache --save-snapshot ../tmp/worlds-fresh.json --apply

# Osiągnięcia i eliminacje z zapisanych źródeł.
python manage.py refresh_worlds_history --dry-run
python manage.py refresh_worlds_history --apply

# Pobranie zdjęć i aktualizacja ich metadanych w fixture oraz bazie.
python manage.py refresh_player_portraits --apply

# Sprawdzenie kariery i przygotowanie osobnego overlayu.
python manage.py refresh_career_stats --snapshot apps/players/fixtures/leaguepedia_career_snapshot.json.gz --allow-incomplete --dry-run
python manage.py refresh_career_stats --snapshot apps/players/fixtures/leaguepedia_career_snapshot.json.gz --allow-incomplete --output ../tmp/career-stats-overlay.json

# Sprawdzenie historii lig i przygotowanie osobnego overlayu.
python manage.py refresh_leagues --snapshot apps/players/fixtures/leaguepedia_leagues_snapshot.json.gz --dry-run
python manage.py refresh_leagues --snapshot apps/players/fixtures/leaguepedia_leagues_snapshot.json.gz --output ../tmp/leagues-overlay.json
```

`refresh_leaguepedia` bez `--snapshot` pobiera nowe dane. `--dry-run` nie zapisuje plików ani bazy; bez `--apply` i bez `--dry-run` zapisuje fixture oraz raport. Błędy źródła przerywają import zamiast udawać pusty zbiór.

`refresh_worlds_history` domyślnie wykonuje dry run. Obsługuje `--snapshot`, `--eliminations-source`, `--fixture` i `--report`; oba źródła muszą mieć zgodne `as_of`. `--apply` zmienia tylko historię i `worlds_titles_count`, zachowuje zdjęcia i statystyki, tworzy backup w `tmp/worlds-history-backups` i przy błędzie cofa bazę oraz przywraca fixture. Domyślny raport to projektowy `tmp/worlds-history-refresh-report.json`.

`refresh_player_portraits` bez `--apply` przygotowuje metadane i raport; `--source <plik.json>` odtwarza zapisaną odpowiedź bez sieci. Aktualizacja scala tylko pola zdjęcia. Domyślne źródło i raport trafiają do projektowego `tmp/`.

`refresh_career_stats` bez `--snapshot` pobiera nowe agregaty, a `--save-snapshot <plik.json>` zapisuje źródło. Komenda tworzy overlay i nie aktualizuje fixture ani bazy; nie ma `--apply`. Przyjęty overlay należy scalić po trwałym `slug` wyłącznie do `career_stats.career`, a scalony plik zaimportować przez `seed_players --file <plik.json>`. Bez `--allow-incomplete` konflikt zatrzymuje odświeżenie; ta opcja zachowuje niekompletność i nie włącza warunków dla sprzecznych danych.

`refresh_leagues` również tworzy tylko overlay. Bez `--snapshot` pobiera nowe dane; `--dry-run` sprawdza je bez zapisu, a `--output` i `--save-snapshot` wybierają pliki wyniku i źródła (także `.gz`). Przyjęty overlay scala się po trwałym `slug` wyłącznie do `attributes.leagues` i `attributes.leagues_meta`, zachowując pozostałe dane, a następnie importuje scalony plik przez `seed_players --file <plik.json>`.

Świeże źródła historii pobierają funkcje `fetch_achievements_source` oraz `fetch_eliminations_source`; samo wzbogacanie danych nie wykonuje żądań sieciowych. Przy nowym snapshocie trzeba odświeżyć źródła historii do tego samego `as_of`.

## Pakiet do wdrożenia

Migracja `players.0003_release_worlds_players` instaluje zamrożony, sprawdzany przez SHA-256 pakiet `fixtures/releases/worlds_players_2026_10_18_v1.json.gz`. Obejmuje 882 tożsamości, 738 zweryfikowanych zawodników oraz powyższe metadane i statystyki; nie potrzebuje sieci ani ponownego scrapowania. Kolejna aktualizacja źródeł wymaga osobnego wydania zamiast podmiany tego pliku. Szczegóły kalendarza, ochrony postępu i wdrożenia: [DEPLOYMENT.md](DEPLOYMENT.md).

Aktualizacja 19 października ma osobny pakiet `fixtures/releases/worlds_players_2026_10_19_v1.json.gz`; poprzedni plik migracji pozostaje niezmieniony. Migracja `players.0005_worlds_2026_october_19_release` automatycznie instaluje ten pakiet podczas zwykłego `migrate`, sprawdza jego SHA-256 i scala dane po istniejących slugach bez kasowania identyfikatorów, odpowiedzi i wyników. Kontrola wdrożenia porównuje już najnowszy pakiet. Kanoniczny `worlds_players_full.json` zawiera te same nowe dane. Czysta funkcja `refresh_worlds_records` zastępuje sprawdzone agregaty zamiast dodawać różnice; ponowne uruchomienie z tymi samymi źródłami nie nalicza map ani championów drugi raz. Zachowuje nazwiska, role, zdjęcia, ligowe źródła i pozostałe metadane oraz kariery niewymienione w częściowym eksporcie.
