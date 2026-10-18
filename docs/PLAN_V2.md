# Worlds XI – Plan wersji 2

Data: 2026-08-16 · Repo `kontra` (Django + DRF / Next.js 14 / scraper Leaguepedia)
Rewizja: 2 (usunięto warunki relacyjne i osiągnięciowe odrzucone przez właściciela projektu)

---

## 1. Cel i stan wyjściowy

Gra typu "Mundialowa Jedenastka" w realiach League of Legends: codzienna plansza z 5 slotami
(Top / Jungle / Mid / ADC / Support), każdy slot ma 2–3 warunki, gracz zgaduje zawodnika,
który **historycznie grał na Worlds** i spełnia wszystkie warunki. Punktacja premiuje rzadkie,
poprawne odpowiedzi.

Co działa i zostaje:
- baza 876 graczy Worlds S1–S15 (Leaguepedia Cargo), auto-seed przy starcie kontenera
- API: `dailies/today`, `submissions/answer` (weryfikacja slot po slocie), leaderboard, archiwum
- frontend: mapa Summoner's Rift z 5 węzłami ról, autocomplete zawodników, tryb na żywo

### Co jest zepsute (audyt kodu, 2026-08-16)

**Backend – punktacja jest niesprawna u źródła:**

1. `SubmissionAnswer.points_awarded` to `IntegerField`, a kod zapisuje do niego floaty (`99.9`)
   → cicha utrata precyzji przy każdym zapisie.
2. Odjęcie liczone jest jako `100 - rarity_percent`, ale `rarity_percent` w momencie
   odpowiedzi jest **zawsze `None`** (rarity liczy dopiero nocny job) → każdy gracz dostaje
   dokładnie `-100` za każdą poprawną odpowiedź. Wynik każdego gracza jest identyczny,
   rzadkość picku nie ma żadnego wpływu. To unieważnia całą mechanikę gry.
3. `total_points` zapisywane jako `int(score * 10)` (5000 = 500.0 pkt), ale
   `/score-distribution/` i leaderboard zwracają surową wartość → oś wykresu i ranking
   pokazują liczby 10× za duże.
4. Dwa sprzeczne modele punktacji w jednym repo: silnik liczy "500 minus odjęcia, niżej =
   lepiej", a `scoring/views.py` sortuje ranking rosnąco po punktach ("wyżej = lepiej")
   i `ScoringConfig` trzyma tabelę punktów za tier (10/25/60/120). Pomoc w UI opisuje
   jeszcze trzeci wariant.
5. `IntegrityError` używany w `submissions/serializers.py` bez importu → `NameError`
   przy równoległym zapisie do tego samego slotu.

**Backend – walidacja odpowiedzi jest zbyt pobłażliwa:**

6. `player_matches_slot()` **całkowicie ignoruje rolę slotu** (jest komentarz "role is
   informational") → można wstawić supporta na slot topa i dostać punkty.
7. Nieznany typ warunku zwraca `True`; `champion_played` i `birth_year_range` zwracają
   `True` przy braku danych → warunki, dla których brakuje danych, są po cichu pomijane
   zamiast zawężać pulę.
8. `worlds_champion` ma zaszytą na sztywno listę ~50 nicków mistrzów, a `coach` ma regułę
   "zaakceptuj kkOmę dla każdego Koreańczyka". To zgadywanie zamiast danych.

**Frontend – mocki i sprzeczne liczby:**

9. `page.tsx`: wynik `127` udawany, gdy API nie odpowie; `totalPlayers={1247}` na sztywno;
   licznik błędów liczony heurystyką `5 - poprawne`, mimo że store trzyma prawdziwe `errors`.
10. `ResultsChart`: przy braku danych rysuje wymyślony histogram i podpisuje go "dane demo".
11. Trzy różne wartości maksymalnej liczby błędów w kodzie (5, 10, 12).
12. `useMySubmission` odpytuje API co 5 s w nieskończoność, także po zakończeniu gry.
13. `HelpModal` opisuje punktację, której kod już nie używa.

**Frontend – nadmiar informacji:** ten sam skład 5 slotów jest wyświetlony na ekranie
**cztery razy**: węzły na mapie, pasek warunków pod mapą, siatka "WYNIKI LIVE",
oraz tooltipy. Do tego legenda "pick % → strata", pasek statusu, karta "Twoje staty"
z samymi myślnikami, karta "Tip", Top 10 i archiwum — wszystko na jednym ekranie.

---

## 2. Pętla rozgrywki (docelowa)

1. Wejście → od razu plansza dnia: mapa + 5 węzłów ról z warunkami. Zero scrolla do grania.
2. Klik w węzeł → panel wyboru: warunki slotu + wyszukiwarka zawodników.
3. Trafienie → slot zamyka się na stałe, pokazuje tier rzadkości i procent wyborów.
   Pudło → spada licznik błędów, slot zostaje otwarty, można próbować dalej.
4. Koniec gry: 5 trafień albo 10 błędów → podsumowanie z rozkładem wyników.
5. Nowy daily o północy; archiwum wcześniejszych plansz bez wpływu na ranking.

Tryb `after_close` znika z UI i z modelu — zostaje wyłącznie tryb na żywo.

### Model punktacji (jeden, ostateczny)

Wyżej = lepiej. Za każdą poprawną odpowiedź punkty zależą od tego, jak wielu graczy
wybrało tego samego zawodnika na ten slot:

| Tier | Udział wyborów | Punkty |
|---|---|---|
| Common | > 20 % | 10 |
| Rare | 10–20 % | 25 |
| Epic | 1–10 % | 60 |
| Legendary | < 1 % | 120 |
| Diamond Pick | pierwszy wybór danego zawodnika na ten slot | +50 |

Wartości pochodzą z `ScoringConfig` (edytowalne w adminie). Procent liczony jest na żywo
spośród poprawnych odpowiedzi na dany slot; przy próbie mniejszej niż 25 odpowiedzi wynik
jest oznaczony jako wstępny, a nocny `score_daily` przelicza wszystko od nowa.

---

## 3. Rozbudowa puli warunków

Zasada: warunek musi być **zgadywalny** — gracz ma skojarzyć zawodnika po fakcie, który fani
kojarzą ("grał w G2", "Polak", "wygrał Worlds"), nie po statystyce, której nikt nie pamięta.
Każdy warunek dostaje trudność, a generator składa slot tak, by liczba pasujących kandydatów
mieściła się w widełkach 8–150.

### 3.1. Istniejące (zostają)

rola slotu (od teraz **egzekwowana**), region / residency (LCK, LPL, LEC, LCS, wildcardy),
kraj, kontynent, drużyna, liga, występ na Worlds (rok lub minimalna liczba), mistrz Worlds,
tytuły Worlds ≥ N, występ na MSI, trener, aktywny / emerytowany.

### 3.2. Nowe – kariera i drużyny

- **Grał w drużynie X w roku Y** — precyzyjniejsza wersja "grał w X"
- **Grał na Worlds w barwach ≥ N różnych organizacji**
- **Grał w dwóch różnych ligach głównych** ("i w LEC, i w LCS")
- **Import** — narodowość nie zgadza się z regionem ligi ("Koreańczyk grający w Europie")
- **Debiut na Worlds w roku X**
- **Ostatni Worlds w roku X**
- **Grał na Worlds na dwóch różnych rolach** (Perkz, Bwipo)

### 3.3. Nowe – osiągnięcia

- **Grał w finale Worlds** (niekoniecznie wygrał)
- **Przegrał finał Worlds**
- **Dotarł do półfinału Worlds** (top 4)
- **Wyszedł z fazy grupowej** / **nigdy nie wyszedł z grupy mimo ≥ N występów**
- **Przeszedł przez play-in do fazy głównej** (od 2017)
- **Nigdy nie wygrał Worlds mimo ≥ N występów**
- **Pentakill na Worlds** (dane gol.gg — pula mała, ale efektowna)

### 3.4. Nowe – metryka i konteksty

- **Urodzony przed / po roku X** ("urodzony w latach 90.")
- **Występował na ≥ N edycjach Worlds** (weterani 5+, 7+)
- **Grał na Worlds w erze S1–S3** (trudne, legendarne)
- **Reprezentował region wildcard** (VCS, PCS, LLA, CBLOL, LJL)
- **Grał na Worlds w tym samym roku, w którym jego drużyna debiutowała**

### 3.5. Co to oznacza technicznie

- Evaluator rośnie z 15 do ~30 typów. Większość to zapytania po istniejących tabelach
  (`TournamentAppearance`, `PlayerTeamHistory`) i po `attributes` JSONB.
- Znika zasada "nieznany warunek = spełniony". Nieznany typ warunku od teraz **nie**
  przepuszcza gracza i jest logowany — brak danych ma być widoczny, nie zamiatany.
- Znikają zaszyte listy mistrzów i reguły awaryjne dla trenerów — zastępuje je import danych.
- Generator: pule ważone trudnością (2 sloty łatwe, 2 średnie, 1 trudny), zakaz powtórzenia
  motywu w oknie 14 dni, twarde widełki kandydatów 8–150 sprawdzane zapytaniem SQL,
  a nie iteracją po 500 obiektach w Pythonie.

---

## 4. Przeprojektowanie frontendu

### 4.1. Zasady wizualne

- **Zero emoji.** Obecnie w UI jest ich kilkadziesiąt (💎 ⏳ ✅ 🔥 🏆 ⭐ 🔵 🟣 🟡 flagi krajów,
  ikony ról). Statusy i rzadkość komunikujemy kolorem, typografią i płaskimi SVG.
- **Zero pigułek i kółek.** Koniec z `rounded-full`, pill-buttonami, okrągłymi badge'ami
  i okrągłymi węzłami ról. Język kształtów: **ostre prostokąty ze ściętym narożnikiem**
  (`clip-path`, 6–10 px), cienkie linie 1 px, podwójne obramowanie na elemencie aktywnym.
- Paleta: granat `#0A0E13`–`#0f141b`, złoto `#C89B3C` wyłącznie jako akcent i wynik,
  tiery rzadkości mają własne kolory i nic poza tym ich nie używa.
- Typografia: nagłówki krojem display (Marcellus / Cormorant jako darmowy odpowiednik
  Beaufort), reszta bezszeryfowa. Wersaliki z rozstrzeleniem zamiast ikonek.
- Flagi krajów i ikony ról jako płaskie SVG (ikony ról są już w `image-search/`).

### 4.2. Odchudzenie ekranu głównego

Na ekranie gry zostaje: pasek górny (data, wynik, błędy), mapa z 5 węzłami, panel wyboru
po kliknięciu, i — dopiero po zakończeniu — podsumowanie.

| Element dziś | Decyzja |
|---|---|
| Siatka "WYNIKI LIVE" (5 kafli) | usunąć — duplikuje węzły na mapie |
| Pasek warunków pod mapą | usunąć — duplikuje tooltipy i panel wyboru |
| Legenda "pick % → strata" | usunąć — wynika z modelu punktacji, jest w pomocy |
| Karta "Twoje staty" (same myślniki) | usunąć — wraca z prawdziwym logowaniem, na `/profile` |
| Karta "Tip: rzadkie picki…" | usunąć — jednorazowy onboarding przy pierwszej wizycie |
| Top 10 na ekranie gry | przenieść do podsumowania i na `/leaderboard` |
| Archiwum na ekranie gry | osobna strona `/archiwum`, na głównej tylko odnośnik |
| "Tryb: Na żywo" | usunąć — jest tylko jeden tryb |
| Pasek statusu z 6 licznikami | zwinąć do paska górnego: wynik, trafienia, błędy |

### 4.3. Naprawa bugów wyświetlania

Do usunięcia punkt po punkcie: mock `127`, `totalPlayers={1247}`, mockowy histogram,
heurystyka licznika błędów, trzy różne wartości maksimum błędów, wieczny polling,
stan `submitted` nieprzypisany do konkretnego daily, `locale` w lokalnym `useState`
(gubi się przy nawigacji), pozycjonowanie tooltipa przez `pos.top.includes('7')`.

Zasada nadrzędna: **każda liczba na ekranie pochodzi z API.** Dopóki nie ma danych,
pokazujemy myślnik, nigdy wymyśloną wartość.

---

## 5. Backend – zmiany pod V2

- `points_awarded` → `FloatField`; `total_points` przestaje być mnożone przez 10.
- Rzadkość liczona **w momencie odpowiedzi** (z flagą `is_provisional` przy małej próbie),
  nocny `score_daily` przelicza całość.
- Jeden model punktacji w kodzie, w adminie i w pomocy w UI.
- Rola slotu egzekwowana w `player_matches_slot()`.
- Brakujący import `IntegrityError`.
- Historia prób (`SubmissionAttempt`: slot, gracz, wynik, znacznik czasu) — pozwala liczyć
  błędy po stronie serwera i uczciwie limitować grę do 10 pomyłek.
- Antycheat minimum: autocomplete nie zdradza atrybutów, weryfikacja wyłącznie serwerowa,
  limit zapytań na `guess`.

## 6. Dane – plan uzupełnienia

1. Pełny przebieg scrapera (dziś 78 % graczy ma komplet metadanych) + ręczna korekta top 100.
2. Import brakujących: tytuły Worlds, wyniki i miejsca w turniejach (finały, półfinały,
   wyjścia z grupy), tytuły MSI, trenerzy (z okresów drużynowych).
3. Statyczne pliki kuratorskie w repo: pentakille na Worlds.
4. Skrypt walidacji spójności (gracz z tytułem musi mieć występ w tym roku itd.) w CI.

---

## 7. Etapy prac

**Etap A – Punktacja i walidacja (fundament)**
Jeden model punktacji end-to-end, rzadkość liczona na żywo, `FloatField`, egzekwowanie roli,
koniec z pobłażliwym evaluatorem, brakujący import. Bez tego reszta nie ma sensu — dziś
wszyscy gracze dostają identyczny wynik.

**Etap B – Sprzątanie frontu**
Usunięcie mocków i zdublowanych sekcji, jeden licznik błędów, naprawa bugów z 4.3,
usunięcie emoji i `rounded-full`.

**Etap C – Dane**
Pełny scraper, miejsca w turniejach, tytuły, trenerzy, walidacja w CI.

**Etap D – Nowe warunki + generator**
Typy z sekcji 3 w evaluatorze, generator z wagami trudności i pamięcią 14 dni,
podgląd liczby kandydatów w adminie.

**Etap E – Szlif wizualny**
Ścięte narożniki, typografia display, ikony SVG ról i tierów, flagi SVG, animacje
trafienia i pudła, QA na urządzeniach mobilnych.

**Etap F – Wokół gry**
Archiwum jako pełna strona, leaderboard, profil po zalogowaniu (OAuth), streaki.

Kolejność jest celowa: A naprawia grę, B czyni ją czytelną, C daje paliwo dla D,
E robimy raz, po ustabilizowaniu układu.

---

## 8. Miary sukcesu

- Dwóch graczy z różnymi składami ma różne wyniki (dziś mają ten sam).
- Zero wymyślonych liczb w UI — każda pochodzi z API albo jest myślnikiem.
- Rola slotu jest egzekwowana; support nie przechodzi na slocie topa.
- Pula typów warunków ≥ 30; żaden motyw nie powtarza się w oknie 14 dni;
  każdy slot ma 8–150 kandydatów.
- Brak błędów hydration w konsoli, Lighthouse mobile ≥ 90.
