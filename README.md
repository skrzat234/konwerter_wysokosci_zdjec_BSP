# konwerter_wysokosci_zdjec_BSP
Konwersja wysokości zdjęć z elipsoidalnych na EVRF2007-NH lub KRON86, oraz aktualizacja metadanych EXIF.

Narzędzie przetwarza folder ze zdjęciami z drona - oblicza wysokości normalne na podstawie modelu geoidy i aktualizuje wysokość w metadanych EXIF - bez ingerencji w piksele zdjęć.
Skrypt najpierw tworzy nowy folder równoległy (*_converted_H), kopiuje do niego oryginalne pliki JPG, a następnie wykonuje modyfikacje EXIF wyłącznie na kopiach - pliki źródłowe pozostają nienaruszone.


## Funkcje

- Kopiuje wszystkie zdjęcia .JPG z katalogu źródłowego do nowego folderu *_converted_H.
- Odczytuje współrzędne oraz wysokość elipsoidalną z metadanych EXIF
- Konwertuje wysokości elipsoidalne do EVRF2007-NH lub KRON86 na podstawie modelu geoidy w formacie TXT
- Zapisuje oryginalne i przeliczone metadane (nazwa zdjęcia, współrzędne poziome, wysokości) do pliku TXT
- Aktualizuje pole GPSAltitude w EXIF skopiowanych zdjęć


## Model geoidy

Repozytorium wykorzystuje modele quasi-geoidy EVRF2007-NH i KRON86 dla Polski. Są zapisane w pliku TXT i zawierają trzy kolumny:<br>
"Szerokosc, Dlugosc, Zeta"<br>
Pierwszy wiersz pliku jest traktowany jako nagłówek i jest automatycznie pomijany podczas wczytywania.<br>
Skrypt automatycznie odczytuje plik modelu i interpoluje wartości wysokości dla każdego zdjęcia.

Źródło danych:
Główny Urząd Geodezji i Kartografii (GUGiK)<br>
Model geoidy EVRF2007 został wykorzystany w formie niezmienionej, a w modelu do uzyskania wysokości KRON86 został dostosowany nagłówek by mieścił się w pierwszym wierszu. 

Licencja:
Creative Commons Uznanie Autorstwa 4.0 (CC BY 4.0)
https://creativecommons.org/licenses/by/4.0/

Oryginalny plik:
[Model_quasi-geoidy-PL-geoid2021-PL-EVRF2007-NH]
https://www.gov.pl/web/gugik/modele-danych
