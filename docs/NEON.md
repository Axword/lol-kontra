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

Kod przeglądarki nie otrzymuje danych połączenia z PostgreSQL. Publiczny jest wyłącznie `NEXT_PUBLIC_API_URL`, czyli adres Django API. Zmienne `DATABASE_*`, hasła i klucze Neon pozostają w środowisku backendu. Na Vercelu nadal potrzebny jest publiczny adres HTTPS Django; konfiguracja bazy Neon sama go nie tworzy.

## Potwierdzona weryfikacja

W lokalnym uruchomieniu z bazą Neon potwierdzono:

- Build frontendu, 119 testów frontendu i 120 testów wybranego zakresu backendu zakończyły się powodzeniem.
- Wydanie na gałęzi `production` zawiera 882 rekordy graczy, w tym 738 zweryfikowanych uczestników Worlds, 31 plansz i 310 oznaczonych składów testowych. Nie przenoszono kont użytkowników.
- Test gry obejmujący błędną odpowiedź i pięciu różnych poprawnych graczy zakończył się wynikiem 270 punktów: `500 − (50 + 40 + 50 + 40 + 50)`. Transakcję testową cofnięto.
- Połączenia direct i pooled raportowały aktywne TLS. Ponowne wykonanie `bootstrap_database` nie zmieniło sum kontrolnych ośmiu sprawdzonych tabel.
- Ograniczona rola aplikacji nie mogła wykonywać DDL ani zapisywać historii migracji.
- Migracje najpierw sprawdzono na podrzędnej gałęzi testowej, którą następnie usunięto. Pozostała tylko gałąź `production`.
- Uruchomiony frontend (`http://localhost:3000/`) i API (`http://localhost:8000/api/v1/dailies/today/`) zwracają HTTP 200. W przeglądarce sprawdzono planszę oraz wyszukiwanie zawodnika ze zdjęciem.
- Lokalny test `tests.deploy_smoke` sprawdził migracje od zera, zachowanie postępu przy ponownym wdrożeniu i uprawnienia rzeczywistej roli aplikacji. Losową bazę i rolę testową usunięto.

W Vercelu ustawiono już publiczny adres API dla Production i Preview. Wdrożenie nowej konfiguracji Rendera pozostaje w toku; wymagane zmienne i kontrolę po uruchomieniu opisuje [RENDER.md](RENDER.md). Powyższe lokalne wyniki nie potwierdzają uruchomienia nowej konfiguracji na Renderze.

## Integracje narzędzi agentów

Instalacja CLI 8.8.0 skonfigurowała globalne integracje dla Codex, Claude, Cursor i VS Code oraz dziewięć umiejętności Neon. Dla Cline, Copilot i Zed zapisano integracje MCP jako ścieżkę zapasową. Istniejące pozostałe wpisy konfiguracji zachowano.

W konfiguracji Codex plugin `neon-postgres@plugins-cli` jest włączony, a jego pakiet wskazuje endpoint OAuth `https://mcp.neon.tech/mcp`. Narzędzia tego MCP nie są dostępne w bieżącej sesji; instalacja i włączenie pluginu nie potwierdzają zalogowania przez OAuth.
