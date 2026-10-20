# Widoczność w Google

Główna domena gry: https://lol-kontra.axword.pl/.
Usługę z tym prefiksem potwierdzono w Search Console 20.10.2026 na koncie
właściciela. Publiczny tag HTML znajduje się w `metadata.verification.google`
w `frontend/app/layout.tsx`; nie usuwaj go przy kolejnych wdrożeniach.
Tego dnia Google pomyślnie przetworzyło `/sitemap.xml` i wykryło dwie strony.
Test wersji opublikowanej w Search Console potwierdził dostęp Google do strony
głównej i możliwość jej indeksowania. To nie oznacza jeszcze obecności w indeksie.
Ręczną prośbę o indeksację strony głównej przyjęto 20.10.2026; Search Console
potwierdziło dodanie adresu do priorytetowej kolejki. Pierwszy błąd połączenia
reCAPTCHA ustąpił po odświeżeniu panelu. Nie ponawiaj zgłoszenia dla podniesienia
priorytetu — Google wskazuje, że kolejne prośby go nie zmieniają.
Frontend udostępnia `/robots.txt` i `/sitemap.xml`. Mapa obejmuje stronę główną
i archiwum. Strona główna ma wskazany adres kanoniczny, polski opis gry oraz
tytuł zawierający WORDS V, League of Legends i Worlds. Opis jest dostępny także
w początkowym HTML, zanim pobierze się plansza. API i panel administracyjny są
wyłączone z crawlowania w robots.txt; ich ochrona nie zależy od robots.txt.

W Google Search Console dodaj usługę z prefiksem `https://lol-kontra.axword.pl/`.
Potwierdź własność metodą wskazaną przez Google na koncie właściciela. Publiczny
znacznik weryfikacyjny ma pozostać na stronie po weryfikacji. Następnie w sekcji
„Mapy witryn” zgłoś `https://lol-kontra.axword.pl/sitemap.xml`, a w sprawdzaniu
adresu URL poproś o zindeksowanie strony głównej. Google decyduje o indeksacji;
zgłoszenie mapy nie gwarantuje terminu ani miejsca w wynikach.

Nie dodawaj metatagu `noindex` ani globalnej blokady `/` w produkcji.
Po zmianie domeny zaktualizuj metadataBase, adres kanoniczny, robots i sitemap
oraz usługę w Search Console. Nie umieszczaj kluczy konta Google w aplikacji.
