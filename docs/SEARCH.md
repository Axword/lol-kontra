# Widoczność w Google

Główna domena gry: https://lol-kontra.axword.pl/.
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
