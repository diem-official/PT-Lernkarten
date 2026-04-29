1. Gesamtarchitektur (Die Split-Architektur)

Das System ist streng in zwei voneinander isolierte Phasen getrennt:

    Data Ingestion Pipeline (Lokal auf Threadripper): Ein rechenintensiver Vorab-Prozess, der Bilder analysiert, bereinigt und strukturierte Daten erzeugt.

    Static Web Application (Frontend auf Webspace): Eine leichtgewichtige, rein clientseitige Web-App (HTML/CSS/JS), die von den generierten Daten angetrieben wird.

2. Phase 1: Lokale Datenaufbereitung (Die Pipeline)

Dieses Modul läuft ausschließlich auf deiner Hardware (Nvidia RTX 3090 Ti) und bereitet die Lernmaterialien vor.

Eingabedaten:

    Bilder in gängigen Formaten (JPG, PNG, TIFF).

    Strikte Namenskonvention für das Routing: Kategorie-Unterkategorie-Ansicht.endung (Beispiel: Knochen-Arm-dorsal.jpg).

Verarbeitungsschritte:

    Texterkennung (OCR): Das Bild wird an eine lokale OCR-Engine (z. B. PaddleOCR) übergeben. Das System erfasst jeden Textblock und extrahiert den String (den Begriff) sowie die Bounding-Box-Koordinaten (X-Achse, Y-Achse, Breite, Höhe).

    Bildbereinigung (Inpainting): Das Originalbild und die Bounding-Box-Koordinaten werden an ein Inpainting-Modell (z. B. LaMa) übergeben. Das Modell nutzt die Koordinaten als Maske und rechnet den Text aus dem Bild heraus, indem es den Hintergrund nahtlos auffüllt. Das bereinigte Bild wird exportiert (z. B. als Knochen-Arm-dorsal-clean.jpg).

    Datenexport (JSON-Generierung): Die Pipeline erstellt eine zentrale JSON-Datei. Diese fungiert als Datenbank für das Frontend. Sie verknüpft den Dateinamen des bereinigten Bildes mit einem Array aus Objekten. Jedes Objekt enthält die Koordinaten (X, Y, Breite, Höhe) und den zugehörigen, korrekten Lösungs-String.

3. Phase 2: Das Frontend Layout (UI Design)

Das UI ist responsiv für Landschaftsformate (Tablets und Laptops) konzipiert. Hochformat wird ignoriert.

Das Grid-Layout (Zwei Spalten):

    Linke Spalte (Navigation): Nimmt ca. 20% bis 25% der Bildschirmbreite ein. Es ist ein vertikales, hierarchisches Akkordeon-Menü.

    Rechte Spalte (Lernbereich): Nimmt den restlichen Platz ein (75% bis 80%). Hier wird das ausgewählte, bereinigte Bild zentriert und so groß wie möglich dargestellt.

Dynamische Menü-Generierung:
Das JavaScript des Frontends liest beim Start die zentrale JSON-Datei ein. Es parst die Dateinamen der Bilder (getrennt durch die Bindestriche) und baut das linke Menü automatisch auf.

    Ebene 1: Kategorie (z. B. Knochen)

    Ebene 2: Unterkategorie (z. B. Arm)

    Ebene 3: Ansicht (z. B. dorsal) -> Dies ist das klickbare Element, welches das entsprechende Bild in den rechten Lernbereich lädt.

4. Phase 3: Die Applikationslogik (Interaktion & Validierung)

Dies beschreibt das Verhalten im rechten Lernbereich, sobald ein Bild aus dem Menü ausgewählt wurde.

Feld-Generierung (Overlay-Technik):
Sobald ein Bild geladen wird, iteriert das Skript über die zugehörigen Koordinaten aus der JSON-Datei. Für jeden Eintrag wird ein leeres HTML-Eingabefeld (Input) als Overlay dynamisch über das Bild gelegt. Die absolute Positionierung und Größe richten sich exakt nach den X/Y-Werten und der Breite/Höhe aus der JSON-Datei. Neben jedem Eingabefeld wird ein runder Button mit einem "?"-Symbol platziert.

Validierungs-Logik (Echtzeit-Prüfung):
Die Eingabe des Nutzers wird permanent (z. B. beim Verlassen des Feldes oder per Tastenschlag) mit dem korrekten String aus der JSON-Datei verglichen. Das System nutzt hierfür einen String-Matching-Algorithmus (wie die Levenshtein-Distanz), um Tippfehler zu erkennen. Groß- und Kleinschreibung wird grundsätzlich ignoriert.

    Status 1 (Falsch/Leer): Keine visuelle Änderung. Das Feld bleibt weiß mit Standard-Rahmen.

    Status 2 (Tippfehler - Orange): Wenn die Levenshtein-Distanz anzeigt, dass die Eingabe zu z. B. 80% bis 95% übereinstimmt (z. B. ein Buchstabendreher), färbt sich der Hintergrund oder der Rahmen des Feldes orange.

    Status 3 (Korrekt - Grün): Wenn die Distanz 0 ist (oder eine 100%ige Übereinstimmung vorliegt, abgesehen von Groß-/Kleinschreibung), färbt sich das Feld sofort grün. Das Feld kann nach erfolgreicher Eingabe gesperrt (read-only) werden, um versehentliches Löschen zu verhindern.

Das Hilfesystem (Der "?"-Button):
Wird der "?"-Button neben einem Feld geklickt, öffnet sich ein kleines Modal-Fenster oder ein fest positionierter Tooltip direkt neben dem Feld. Darin steht der korrekte Begriff in gut lesbarer Schrift. Das Modal blockiert weitere Eingaben im aktuellen Feld, bis der Nutzer den darin befindlichen "Got it"-Button anklickt. Erst dann schließt sich das Modal wieder.

Reset-Logik (Tabula Rasa):
Es gibt keine serverseitige Speicherung des Fortschritts.

    Klickt der Nutzer im linken Menü auf ein anderes Thema, wird der Lernbereich geleert und das neue Bild mit frischen, leeren Feldern geladen.

    Klickt der Nutzer auf das aktuelle Thema oder drückt "F5" (Browser-Reload), wird der DOM (Document Object Model) neu aufgebaut. Alle grünen und orangen Markierungen verschwinden, alle Eingaben werden gelöscht.
