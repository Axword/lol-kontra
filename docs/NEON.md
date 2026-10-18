# Neon i uruchamianie projektu

Konfigurację Neon zainicjalizowano CLI 8.8.0 dla projektu `hidden-math-61798935`, gałąź `production`. Lokalny kontekst znajduje się w ignorowanym `.neon`, a deklaracja usług w `neon.ts`. `neon deploy` zastosował tę deklarację; migracje i dane Django są osobnym krokiem opisanym w [DEPLOYMENT.md](DEPLOYMENT.md).

Istniejące integracje i umiejętności agentów zostały zainstalowane przez `neon init`. Przy dalszej pracy używaj tego samego projektu i kontekstu, bez ponownego inicjalizowania lub instalowania integracji.

## Polecenia z katalogu głównego

```sh
npm ci
npm --prefix frontend ci
npm run build
npm test
npm run lint
```

Pierwsze polecenie instaluje narzędzia Neon z głównego locka, drugie zależności frontendu. `build`, `test` i `lint` przekazują pracę do istniejącego projektu `frontend`; nie wykonują migracji ani nie uruchamiają API. Test obejmuje także blokadę konfiguracji Vercela. Frontend nadal komunikuje się przez Axios z Django, a Django łączy się z PostgreSQL.

## Połączenia i sekrety

| Zmienna w głównym `.env` | Zastosowanie |
| --- | --- |
| `DATABASE_URL` | Wygenerowane przez Neon połączenie pooled; zachowaj je przy pobieraniu konfiguracji CLI. |
| `DATABASE_URL_UNPOOLED` | Bezpośrednie połączenie właściciela do migracji i kroku wydania; potrzebne także do sesyjnej blokady PostgreSQL. |
| `DATABASE_RUNTIME_URL` | Połączenie osobnej, ograniczonej roli dla API i procesów Celery. |
| `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` | Dane tej samej ograniczonej roli; jeśli podane, muszą zgadzać się z `DATABASE_RUNTIME_URL`. |
| `NEON_BRANCH` | Kontekst gałęzi zapisany przez CLI. |

Pobranie konfiguracji CLI zapisało trzy klucze zarządzane przez Neon: `DATABASE_URL`, `DATABASE_URL_UNPOOLED` i `NEON_BRANCH`. Wcześniejszą lokalną konfigurację zachowano w prywatnej kopii. `DATABASE_RUNTIME_URL` jest ustawieniem aplikacji i musi wskazywać osobne konto z potrzebnymi grantami, bez prawa do DDL i bez praw administratora. Nie zastępuj go kontem właściciela.

Według [dokumentacji Neon](https://neon.com/docs/connect/connection-pooling), pooled połączenia obsługują zwykły ruch aplikacji, natomiast migracje, kopie i operacje wymagające stanu sesji używają połączenia direct. Zachowaj opcje TLS dostawcy. Dokładny wybór połączenia przez procesy Django opisuje [instrukcja wdrożenia](DEPLOYMENT.md#neon).

Główny `.env`, lokalny kontekst `.neon` i kopie sekretów pozostają poza Gitem. [CLI `neon env pull`](https://neon.com/docs/cli/env) aktualizuje zmienne Neon w pliku środowiskowym; przed kolejnym pobraniem zachowaj prywatną kopię i sprawdź docelowy plik. Nie publikuj zawartości plików ani connection strings w logach.

Kod przeglądarki nie otrzymuje danych połączenia z PostgreSQL. Publiczny jest wyłącznie `NEXT_PUBLIC_API_URL`, czyli adres Django API. Zmienne `DATABASE_*`, hasła i klucze Neon pozostają w środowisku backendu. Frontend Vercela używa `https://lol-kontra.onrender.com/api/v1`; API działa na Renderze.

## Potwierdzona weryfikacja wcześniejszego wdrożenia

Poniższe wyniki dotyczą wdrożenia z 18.10.2026, sprzed usunięcia syntetycznych głosów i zmiany prezentacji rzadkości:

- Build frontendu i 119 testów frontendu przeszły. Pełny zestaw backendu na odizolowanej lokalnej bazie testowej: 431 PASS, 175 ostrzeżeń, 187,48 s.
- Wydanie na gałęzi `production` zawierało 882 tożsamości, 738 zweryfikowanych uczestników Worlds, 733 zdjęcia, 737 kompletnych statystyk kariery i 31 plansz. Nie przenoszono kont użytkowników.
- Historyczny test gry obejmujący błędną odpowiedź i pięciu różnych poprawnych graczy zakończył się wynikiem 270 punktów: `500 − (50 + 40 + 50 + 40 + 50)`. Udziały pochodziły wtedy z oznaczonych składów testowych; ten wynik nie jest oczekiwaniem dla obecnej gry. Transakcję testową cofnięto.
- Połączenia direct i pooled raportowały aktywne TLS. Ponowne wykonanie `bootstrap_database` nie zmieniło sum kontrolnych ośmiu sprawdzonych tabel.
- Ograniczona rola aplikacji nie mogła wykonywać DDL ani zapisywać historii migracji.
- Migracje najpierw sprawdzono na podrzędnej gałęzi testowej, którą następnie usunięto. Pozostała tylko gałąź `production`.
- Uruchomiony frontend (`http://localhost:3000/`) i API (`http://localhost:8000/api/v1/dailies/today/`) zwracają HTTP 200. W przeglądarce sprawdzono planszę oraz wyszukiwanie zawodnika ze zdjęciem.
- Lokalny test `tests.deploy_smoke` sprawdził migracje od zera, zachowanie postępu przy ponownym wdrożeniu i uprawnienia rzeczywistej roli aplikacji. Losową bazę i rolę testową usunięto.

Wcześniejsze wdrożenie `e686188` działało na Vercel Production i Renderze; adres API ustawiono dla Production i Preview. Publiczna kontrola odczytu oraz Chrome potwierdziły jasny interfejs, planszę i wyszukiwanie Fakera ze zdjęciem. API działa z PostgreSQL i prywatnym cache Redis. Nie zapisywano danych użytkowników podczas tamtej kontroli. Osobny worker i scheduler Celery nie są wdrożone; nie utworzono płatnych zasobów. Szczegóły i odtwarzanie konfiguracji opisuje [RENDER.md](RENDER.md).

## Aktualizacja bez syntetycznych głosów

Aktualne migracje zachowują zamrożone wydanie, a następną migracją usuwają wyłącznie rozgrywki `is_seed` i ich odpowiedzi. Docelowo świeża baza po wszystkich migracjach zawiera 31 plansz i zero syntetycznych rozgrywek. Istniejące prawdziwe rozgrywki pozostają w bazie. Algorytmy procentów wyboru i statystyk dodatkowo pomijają `is_seed`, a `prepare_month` domyślnie nie dodaje głosów i odrzuca dodatnie `--voters`.

19.10.2026 backend `3da0ff0` osiągnął Render Live. Migracje na Neon usunęły 310 oznaczonych syntetycznych rozgrywek i dodały profile gości. Kontrola publicznego API potwierdziła brak sztucznych głosów, prawdziwy rozkład wyników, moderację nicków oraz ponowne otwarcie ośmiu historycznych ukończonych plansz z zachowanymi składami i punktami. Zakończenie nowej gry archiwalnej nie przelicza poprzednich graczy. Świeży test migracji oraz 448 testów backendu przeszły poprawnie. Początkowe 0% przy braku wcześniejszych wyborów jest prawidłowe.

Aktualizacja WORDS V: backend `0f78ae4` osiągnął Live 19.10.2026 po migracji `scoring.0006_uncommon_and_permanent_first_picks`. Kontrola porównała 40 prawdziwych gier, 179 odpowiedzi i 245 prób z kopią sprzed migracji: punkty, wybory i postęp pozostały zachowane. Zweryfikowano 104 trwałe pierwsze trafienia; nowe metadane nie dodają premii punktowej. Zapisane odpowiedzi zwracają zdjęcia zawodników również przy ponownym otwarciu planszy.

## Integracje narzędzi agentów

Instalacja CLI 8.8.0 skonfigurowała globalne integracje dla Codex, Claude, Cursor i VS Code oraz dziewięć umiejętności Neon. Dla Cline, Copilot i Zed zapisano integracje MCP jako ścieżkę zapasową. Istniejące pozostałe wpisy konfiguracji zachowano.

W konfiguracji Codex plugin `neon-postgres@plugins-cli` jest włączony, a jego pakiet wskazuje endpoint OAuth `https://mcp.neon.tech/mcp`. Narzędzia tego MCP nie są dostępne w bieżącej sesji; instalacja i włączenie pluginu nie potwierdzają zalogowania przez OAuth.
