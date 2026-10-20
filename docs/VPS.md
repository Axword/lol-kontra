# WORLDS KONTRA na jednym VPS

Przygotowany wariant dla **Ubuntu 24.04 lub 26.04 LTS**: Next.js, Django/Gunicorn, Celery, Redis,
PostgreSQL i Caddy. Jedna domena wystarcza: `/` obsługuje frontend, `/api/v1/` API,
`/admin/` panel Django. Caddy wystawia tylko porty 80/443 i odnawia certyfikaty.
PostgreSQL i Redis nie mają portów dostępnych z internetu.

Produkcja działa na `https://lol-kontra.axword.pl`, na OVH. PostgreSQL i klucz
tożsamości zostały przeniesione z poprzedniego hostingu. Poniższe kroki migracji
służą odtwarzaniu instalacji na nowym serwerze; nie wykonuj ponownego importu
na działającej bazie. Konfiguracji `compose.vps.yaml` nie łącz z developerskim Compose.

## 1. Zanim uruchomisz serwer

- VPS z Ubuntu 24.04 lub 26.04 LTS, dostęp administracyjny przez SSH na kluczu i konsola ratunkowa OVH.
- Własna domena i możliwość zmiany DNS. Nie potrzeba drugiej domeny dla API.
- Osobny magazyn kopii poza VPS, np. zgodny z S3, z kluczem ograniczonym do backupów.
- Dostęp do obecnego Rendera i Neona. **Zachowaj dokładnie dotychczasowy
  `DJANGO_SECRET_KEY` z Rendera**. Z tego klucza powstają identyfikatory profili gości;
  nowy klucz utraci powiązania z nickami i odznakami mimo przeniesienia tabel.
- Sprawdź wersję PostgreSQL źródła (`SHOW server_version;` w konsoli SQL Neona).
  Zestaw obsługuje 16, 17 i 18; ustaw tę samą wersję przed pierwszym uruchomieniem bazy.
  Konfigurator dla 18 ustawia `POSTGRES_VOLUME_TARGET=/var/lib/postgresql`, zgodnie
  z katalogiem danych oficjalnego obrazu. Dla 16/17 pozostaje `/var/lib/postgresql/data`.
  Nie zmieniaj wersji ani miejsca montowania istniejącego wolumenu bez migracji.
  Inna wersja wymaga osobno sprawdzonego wariantu migracji. Zmiana numeru obrazu
  na istniejącym wolumenie **nie wykonuje aktualizacji PostgreSQL**.

Hasła kont, użytkownicy, tokeny gości, rozgrywki, próby, procenty, diamenty,
komentarze i historia migracji są przenoszone przez pełny dump bazy. Pliki `media/`
trzeba skopiować oddzielnie. Hasła kont nie są resetowane. Ciasteczka i localStorage
nie przechodzą między domenami; użytkownik konta loguje się ponownie.

Goście przed wyłączeniem starej strony zapisują **Profil → Zapisz dostęp do profilu**.
Po skopiowaniu bazy na nowej domenie wybierają **Wczytaj dostęp do profilu**, sprawdzają
nick/liczbę gier i zatwierdzają. Plik jest prywatnym kluczem dostępu, nie kopią
punktów; serwer pobiera wyniki z bazy. Bez tego pliku lub dostępu do starej
przeglądarki nie da się bezpiecznie wskazać, który anonimowy profil należy do osoby.
Profile nie są automatycznie łączone. Zachowaj starą stronę przez okres przejściowy.

## 2. Przygotowanie Ubuntu

Najpierw sprawdź klucz SSH w drugim oknie i pozostaw pierwsze połączenie otwarte.
Poniższe polecenia wykonuje administrator na **nowym VPS**, nie na komputerze lokalnym:

```bash
sudo -i
git clone https://github.com/Axword/lol-kontra.git /root/words-v-setup
cd /root/words-v-setup
bash infra/vps/provision.sh
```

Skrypt aktualizuje Ubuntu, instaluje Docker z podpisanego repozytorium producenta,
Compose, restic i UFW. Otwiera 22/80/443 TCP, tworzy root-owned katalogi i bare repo.
Nie zmienia hasła SSH ani nie dodaje użytkowników do grupy Docker. Niestandardowy
port SSH wymaga ręcznego dopasowania reguł przed uruchomieniem. Nie wymusza restartu
po aktualizacji systemu; zaplanuj go i później sprawdź usługę.

Po przetestowaniu klucza dla konta `ubuntu`:

```bash
bash infra/vps/harden-ssh.sh ubuntu --key-login-confirmed
```

Skrypt sprawdza konfigurację SSH przed przeładowaniem. Przed zamknięciem poprzedniej
sesji potwierdź ponowne logowanie. Zachowaj dostęp do konsoli OVH.

## 3. Sekrety i domena

Zapisz stary klucz Django w `/etc/words-v/previous-django-secret` (root, tryb 0600),
bez wypisywania go w terminalu, historii poleceń lub rozmowie. Można użyć ukrytego
wejścia `getpass`:

```bash
python3 - <<'PY'
import getpass, os
fd = os.open('/etc/words-v/previous-django-secret', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(getpass.getpass('Dotychczasowy DJANGO_SECRET_KEY z Rendera: '))
PY
python3 infra/vps/configure.py create \
  --domain twojadomena.pl --email admin@twojadomena.pl --postgres-major 17 \
  --django-secret-file /etc/words-v/previous-django-secret
```

Użyj własnej domeny, emaila i sprawdzonej wersji bazy. Konfigurator tworzy
`/etc/words-v/app.env`, generuje dwa różne hasła PostgreSQL i nigdy nie nadpisuje
istniejącego pliku. Dla zupełnie nowej, pustej aplikacji istnieje `--new-install`;
**nie używaj tej opcji przy migracji obecnej gry**. Sekrety z `$` są cytowane
dosłownie; plików konfiguracyjnych nie wykonujemy przez `source`.

W DNS ustaw rekord A domeny na IPv4 VPS. Rekord AAAA dodaj tylko dla działającego
IPv6; usuń stary AAAA wskazujący inny serwer. Porty 80/443 muszą być osiągalne
również w firewallu OVH. Nie dodawaj portów 3000/8000/5432/6379.

## 4. Niezależny backup przed pierwszym wdrożeniem

Skopiuj wzór `infra/vps/backup.env.example` do `/etc/words-v/backup.env`, ustaw
adres własnego repozytorium restic i dane dostępu S3. To wartości dosłowne, nie
skrypt powłoki. Losowe hasło szyfrowania umieść w `/etc/words-v/restic-password`.
Oba pliki muszą należeć do roota i mieć tryb 0600. Hasło szyfrowania zachowaj
także poza serwerem, np. w menedżerze haseł; bez niego nie odtworzysz kopii.

```bash
chmod 600 /etc/words-v/backup.env /etc/words-v/restic-password
python3 infra/vps/restic-command.py init
python3 infra/vps/restic-command.py snapshots
```

Codzienny timer restic zapisuje dump, media i zaszyfrowaną konfigurację do magazynu poza
VPS. Domyślnie każda aktualizacja wymaga udanej kopii restic; błąd zatrzymuje wdrożenie.
Sprawdzaj `systemctl status words-v-backup.timer` i
`journalctl -u words-v-backup.service`. Kopie zawierają prywatne dane i klucze.
Magazyn repozytorium i jego hasło również muszą być niezależnie dostępne po awarii VPS.

Zestaw celowo nie usuwa kopii automatycznie. Monitoruj miejsce na dysku i ustal
retencję po zweryfikowaniu odtwarzania; nie kasuj jedynej sprawdzonej kopii.

Obecna instalacja OVH używa codziennej kopii całego VPS u dostawcy oraz sprawdzonego
zadania `words-v-local-backup.service`. Administrator wybiera ten wariant przez
root-owned plik `/etc/words-v/deploy-backup-mode` o prawach 0600, zawierający
`ovh-managed`. Wtedy przed każdą aktualizacją musi udać się dodatkowa kopia lokalna.
Kopia lokalna nie chroni przed utratą całego VPS; kopia OVH powstaje według własnego
harmonogramu, a nie przy każdym wdrożeniu. Nieskonfigurowany timer restic pozostaje
wyłączony. Nie ustawiaj tego trybu na nowym hoście bez działających kopii OVH
i zweryfikowanej usługi lokalnej.

## 5. Przeniesienie z Neona

Najpierw zrób próbę na nowej, pustej bazie; dopiero później zatrzymaj zapisy starej
aplikacji i wykonaj **końcowy dump**. W Renderze zatrzymaj backend, worker i scheduler
lub włącz sprawdzony tryb blokady zapisów. Samo ukrycie przycisków frontendu nie
blokuje API. Nie utrzymuj równolegle dwóch niezależnych baz przyjmujących odpowiedzi.

W `/etc/words-v/neon.pg_service.conf` (root, 0600) umieść dane **bezpośredniego**
połączenia z Neonem, bez `-pooler` w hoście:

```ini
[neon-export]
host=ep-TWOJ-ENDPOINT.eu-central-1.aws.neon.tech
port=5432
dbname=NAZWA_BAZY
user=UZYTKOWNIK_Z_PRAWEM_ODCZYTU_CALEJ_BAZY
password=HASLO_Z_PANELU_NEON
sslmode=verify-full
sslrootcert=/etc/ssl/certs/ca-certificates.crt
```

Nie wklejaj prawdziwego pliku do GitHuba. Eksport używa klienta tej samej głównej
wersji co źródło/cel i przerywa przy niezgodności. Źródłowa baza jest tylko czytana:

```bash
bash infra/vps/export-neon.sh
```

Przygotuj niezmienny katalog wydania przed importem (pełny SHA z przetestowanego mastera):

```bash
SHA=PELNY_40_ZNAKOWY_SHA
git --git-dir=/opt/words-v/repository.git fetch origin master
mkdir /opt/words-v/releases/$SHA
git --git-dir=/opt/words-v/repository.git archive $SHA | tar --no-same-owner --same-permissions -x -C /opt/words-v/releases/$SHA
cd /opt/words-v/releases/$SHA
export RELEASE_SHA=$SHA
docker compose -p words-v --env-file /etc/words-v/app.env -f compose.vps.yaml build db api
docker compose -p words-v --env-file /etc/words-v/app.env -f compose.vps.yaml up -d --wait db redis
bash infra/vps/import-database.sh /var/backups/words-v/neon-DATA.dump
bash infra/vps/restore-check.sh /var/backups/words-v/neon-DATA.dump
```

Import odmawia nadpisania bazy z istniejącymi tabelami i nie działa przy aktywnych
procesach zapisujących. `restore-check.sh` odtwarza kopię w oddzielnej bazie
`restore_check_*`, wykonuje migracje/kontrole aplikacji i usuwa tylko tę bazę testową.
Nie używaj `pg_restore --clean` ani `docker compose down -v` na danych produkcyjnych.

Jeśli próba wykryje nieobsługiwane rozszerzenia Neona, zatrzymaj migrację i dopasuj
eksport/rozszerzenia po analizie błędu. Nie ignoruj błędów przywracania.
Próbnego importu nie traktuj jako finalnego: późniejsze odpowiedzi użytkowników
nie znajdują się w tamtej kopii. Końcowy import wykonujemy do osobnej pustej bazy/
świeżego wolumenu po kontrolowanym przygotowaniu, nie przez nadpisanie działającej bazy.

Przed przełączeniem skopiuj także pliki `media/` do wolumenu `media`, zachowując
prawa zapisu UID/GID 10001. Porównaj liczbę i kontrolne skróty zapisanych rozgrywek,
odpowiedzi, profili i komentarzy. Otwórz stare składy własnego testowego profilu,
sprawdź nick/badge oraz logowanie konta. **Nie przebudowuj historycznych wyników
ani procentów na podstawie bieżącej popularności**. Przechowaj źródłowy dump.

## 6. Pierwsze wdrożenie i kolejne aktualizacje

Po backupie, imporcie i DNS:

```bash
sudo /usr/local/sbin/words-v-deploy PELNY_40_ZNAKOWY_SHA
```

Skrypt pobiera mastera, wymaga dokładnie wskazanego aktualnego commita, buduje obrazy,
robi backup, zatrzymuje procesy zapisujące, uruchamia migracje jako właściciel bazy,
kontrole danych i zbiera static. API działa jako ograniczona rola bez prawa DDL.
Uruchamia frontend/backend i sprawdza publiczny HTTPS, health oraz dzisiejszą planszę.
Udane wydanie staje się `/opt/words-v/current`. Katalogi wydań i trwałe wolumeny
pozostają oddzielne. Aktualizacja wiąże się z krótką przerwą w API.

Po błędzie migracji lub kontroli dostępności skrypt próbuje ponownie uruchomić
poprzednie kontenery i przywrócić wskaźnik wydania. Nie cofa migracji bazy;
zmiany schematu muszą zachowywać zgodność ze starszym kodem. Nieudane wznowienie
wymaga ręcznej kontroli. Dla znanej, zgodnej ze schematem poprzedniej wersji:

```bash
sudo /usr/local/sbin/words-v-deploy POPRZEDNI_ZDROWY_SHA --rollback
```

Rollback pomija migracje i nie cofa zapisanych danych. Jeśli nowy schemat nie jest
zgodny ze starszym kodem, potrzebny jest sprawdzony plan naprawy; odtworzenie starej
kopii wymaga zatrzymania zapisów i oznacza utratę zmian po tej kopii.

Po wdrożeniu sprawdź stronę, logowanie, zapis odpowiedzi, archiwum, profil,
komentarze i ranking. Wykonaj kontrolowany restart VPS, połącz się ponownie i
sprawdź `systemctl status words-v` oraz HTTPS. `start.sh` uruchamia istniejące
kontenery bez ponownego wykonywania migracji.

Dane kont zachowujemy, ale integracje OAuth/SMTP wymagają przeniesienia konfiguracji
i dopisania nowej domeny/callbacków u dostawcy. Ten zestaw nie konfiguruje nowego
dostawcy poczty ani OAuth. Vercel Web Analytics wymaga hostingu/integracji Vercel;
nie zakładamy, że `/_vercel/insights` zacznie zbierać dane na samym VPS.

## 7. GitHub Actions

Workflow `Deploy VPS` działa po zielonym `CI`; również ręczne uruchomienie wymaga
zielonych kontroli `backend`, `frontend`, `infrastructure` dla tego samego SHA.
Automatyczne wdrożenia są domyślnie wyłączone.

Wygeneruj osobny klucz Ed25519. Na serwer prześlij tylko jego część publiczną,
a prywatną umieść w sekrecie środowiska GitHub. Po zatwierdzeniu trwałego dostępu:

```bash
sudo bash infra/vps/configure-deploy-access.sh /sciezka/github-actions-ed25519.pub
```

Powstaje konto `words-deploy`, bez grupy Docker, z zablokowanym hasłem. Katalog
domowy i klucz należą do roota. Wymuszona komenda SSH akceptuje wyłącznie
`deploy PELNY_SHA`; blokuje sesję interaktywną, przekierowania i dowolne polecenia.
Jedyny wpis sudo pozwala uruchomić root-owned `words-v-deploy`; skrypt wymaga
bieżącego commita mastera. Nadal jest to uprawnienie publikacji kodu aplikacji,
więc dostęp do tego repozytorium i środowiska mają tylko zaufane osoby.

W GitHub Environment **vps-production** ogranicz dozwoloną gałąź do **master** i ustaw sekrety:
`VPS_SSH_HOST`, `VPS_SSH_USER`, `VPS_SSH_PORT`, `VPS_SSH_KEY`,
`VPS_SSH_KNOWN_HOSTS`. Odcisk hosta potwierdź przez konsolę OVH lub inne zaufane
połączenie. Workflow wymusza `StrictHostKeyChecking=yes`; nie akceptuje automatycznie
nowych kluczy hosta. `VPS_SSH_USER` ma wartość `words-deploy`. Hasła bazy i klucz
Django pozostają na VPS; workflow ich nie potrzebuje. Po pierwszym sprawdzonym wdrożeniu ustaw repo variable
`VPS_AUTO_DEPLOY=true`. Bez serwera i sekretów nie włączaj automatyzacji.

## 8. Odtwarzanie kopii poza VPS

```bash
sudo python3 /opt/words-v/current/infra/vps/restic-command.py snapshots
sudo python3 /opt/words-v/current/infra/vps/restic-command.py check
sudo python3 /opt/words-v/current/infra/vps/restic-command.py restore \
  --snapshot ID_KOPII --target /var/backups/words-v/recovery-proba1
```

To odzyskuje pliki do nowego prywatnego katalogu, nie nadpisuje bazy aplikacji.
Wskaż odzyskany dump w `restore-check.sh` (najpierw skopiuj go jako plik `.dump`
bezpośrednio pod `/var/backups/words-v`). Regularnie wykonuj taką próbę i test
odtworzenia mediów. Przed uznaniem nowego hostingu za gotowy potrzebny jest
rzeczywisty udany test kopii poza serwerem oraz restartu; same pliki konfiguracji
nie potwierdzają działania zakupionego VPS.

Źródła: [Docker na Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[automatyczny HTTPS Caddy](https://caddyserver.com/docs/automatic-https),
[eksport Neona](https://neon.com/docs/manage/backup-pg-dump),
[pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html),
[restic](https://restic.readthedocs.io/en/stable/040_backup.html).
