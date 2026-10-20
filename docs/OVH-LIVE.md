# Wdrożenie OVH — 20 października 2026

Gra działa pod `https://lol-kontra.axword.pl` na VPS `15.235.90.35`
(Ubuntu 26.04 LTS, 2 vCPU, 4 GB RAM). Frontend, Django, PostgreSQL 18,
Redis, worker, scheduler i Caddy działają w `compose.vps.yaml`.
Publiczne są wyłącznie porty 22, 80 i 443. Baza i Redis nie publikują portów.

Końcowy eksport Neon wykonano po wstrzymaniu Rendera, 20.10.2026 o 11:53 czasu
polskiego. Import zawierał 44 tabele i 9480 rekordów. Suma SHA-256 archiwum:
`9a8515d643ea74b440f51b96cfeab902d443e5f172d60b52725caa8e54f6a5a1`.
Kopia pozostała na komputerze właściciela oraz w prywatnym katalogu VPS.
Próbne odtworzenie w osobnej bazie przeszło kontrolę wydania. Po migracjach
porównano pełną zawartość historycznych gier, odpowiedzi, prób, profili,
komentarzy, statystyk i rozegranych plansz — bez zmian. Zachowano stary klucz
Django; rozpoznano 257 profili powiązanych z historycznymi grami.

Aktualne wydanie wskazuje `/opt/words-v/current`. Skrypty rozwiązują ten symlink
do fizycznego katalogu z SHA, także przy starcie przez systemd. Usługa
`words-v.service` uruchamia zestaw po restarcie bez powtarzania migracji.
Nie wyłączaj logowania hasłem, jeżeli właściciel nie ma własnego sprawdzonego
klucza: tymczasowy klucz wdrożeniowy jest usuwany po zakończeniu prac.
Klucz `codex-vps-20261020` usunięto z `authorized_keys` po zakończeniu wdrożenia;
sprawdzono, że nowe logowanie nim jest odrzucane, i skasowano lokalny klucz.
Hasłowy dostęp właściciela i konsola OVH pozostały dostępne.

OVH Standard ma włączoną codzienną kopię całego VPS o 09:47 UTC, z jednym
punktem przywracania. `words-v-local-backup.timer` przygotowuje codziennie
o 09:30 UTC dodatkowy logiczny dump PostgreSQL, media i prywatną konfigurację.
Pliki mają uprawnienia administratora i są sprawdzane przed zakończeniem zadania.
Nie są automatycznie kasowane. Monitoruj wolne miejsce w `/var/backups/words-v`.

To dwa oddzielne mechanizmy od opcjonalnego restic do własnego magazynu S3/SFTP.
Nieużywany `words-v-backup.timer`, utworzony podczas migracji, wyłączono
20.10.2026 za wyraźną zgodą właściciela. Nigdy nie był uruchomiony i nie miał
konfiguracji magazynu. Włącz go dopiero po skonfigurowaniu i sprawdzeniu restic.
Bez skonfigurowanego magazynu restic nie zgłasza udanego eksportu poza VPS,
a `words-v-deploy` nadal wymaga udanej niezależnej kopii. Nie włączono
automatycznych wdrożeń z GitHuba ani nie utworzono płatnego magazynu kopii.
Przed kolejnym wydaniem skonfiguruj taki magazyn zgodnie z [VPS.md](VPS.md)
albo wykonaj i sprawdź niezależną kopię poza serwerem w kontrolowanym wdrożeniu.

Neon pozostaje w planie Free; Render jest wstrzymany, aby stara baza nie
przyjmowała równoległych zapisów. Stary frontend Vercel pozostaje dostępny
do zapisania pliku dostępu gościa. Ten plik można wczytać w zakładce Profil
na nowej domenie. Profile nie są łączone automatycznie.

Przy zmianie źródła ruchu DNS przeglądarka może przez pewien czas korzystać
ze starego połączenia. Autorytatywny rekord A subdomeny ma TTL 60 sekund.
Pozostałe rekordy domeny i poczta nie były zmieniane w tym wdrożeniu.
