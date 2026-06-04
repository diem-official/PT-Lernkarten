# Design: Bild-Support für Tabellen-Quiz + Einheitliches Dateinamen-Schema

**Datum:** 2026-06-04  
**Status:** Freigegeben

---

## Ziel

1. **Migration** bestehender Clean-Bilder auf ein einheitliches Namensschema mit Subject-Prefix.
2. **Neues Feature**: Optionale Bilder für Tabellen-basierte Text-Quizze (aus Excel-Tabellen erzeugt). Beim Lernen wird das beschriftete OG-Bild gezeigt, beim Testen das Clean-Bild ohne Beschriftungen.

---

## Teil A – Migration bestehender Bilder

### Problem

Die bestehenden Clean-Bilder in `web/data/images/` haben **kein** Subject-Prefix:
- Aktuell: `Bänder-Becken-Dorsal-clean.jpg`
- Soll: `Anatomie 1-Bänder-Becken-Dorsal-clean.jpg`

`process.py` erzeugt bereits `{stem}-clean.jpg` (also MIT Prefix), aber die bestehenden Daten stammen aus einer älteren Version.

### Einheitliche Ableitungsregel (überall)

```
clean_name = og_filename_stem + "-clean.jpg"
```

Beispiele:
- `Anatomie 1-Bänder-Becken-Dorsal.png` → `Anatomie 1-Bänder-Becken-Dorsal-clean.jpg`
- `Anatomie 1-Knochen-Becken-Ventral (Mann).png` → `Anatomie 1-Knochen-Becken-Ventral (Mann)-clean.jpg`

### Migrations-Script `pipeline/migrate_images.py`

1. Unterstützt `--dry-run`-Flag (Standard: Dry-Run aktiv; ohne `--apply` werden keine Änderungen vorgenommen)
2. Liest `web/data/data.json`
3. Legt Backup an: `web/data/data.json.bak` (überschreibt existierendes Backup)
4. Für jeden Eintrag berechnet es den neuen Clean-Namen: `og_stem + "-clean.jpg"`
5. Wenn `old_filename == new_filename`: überspringen (bereits korrekt)
6. Wenn Zieldatei bereits existiert: als "bereits korrekt" behandeln, nur `data.json` aktualisieren, keine Datei-Rename
7. Wenn `old_filename != new_filename` und Quelldatei existiert: umbenennen + Eintrag aktualisieren
8. Wenn `old_filename != new_filename` und Quelldatei **nicht** existiert: Warnung ausgeben, Eintrag trotzdem aktualisieren (Datei wurde möglicherweise bereits extern umbenannt)
9. Schreibt aktualisierte `data.json` zurück (nur bei `--apply`)

**Ausgabe:** Dry-Run listet alle geplanten Änderungen auf. Mit `--apply` werden sie ausgeführt.

---

## Teil B – Bild-Feature für Tabellen-Quiz

### Excel-Format

Eine **optionale Meta-Zeile** als erste Zeile der Excel-Datei:

```
Zeile 1 (Meta):   BILD  |  Anatomie 1-Bänder-Becken-Dorsal.png  |  (leer)
Zeile 2 (Header): Muskel | Ursprung | Ansatz | Funktion | Innervation
Zeile 3+  (Daten): M. gluteus maximus | ... | ...
```

**Erkennung:** Wenn Zelle A1 case-insensitiv `BILD` ist → Meta-Zeile. Zeile 2 wird als Header behandelt.

**Rückwärtskompatibilität:** Tabellen ohne Meta-Zeile funktionieren unverändert.

### JSON-Struktur (`text-data.json`)

Einträge mit Bild bekommen ein optionales `image`-Feld:

```json
{
  "type": "text",
  "subject": "Anatomie 1",
  "category": "Muskeln Detail",
  "subcategory": "Gesäß",
  "view": "Gluteus",
  "image": {
    "og": "Anatomie 1-Bänder-Becken-Dorsal.png",
    "clean": "Anatomie 1-Bänder-Becken-Dorsal-clean.jpg"
  },
  "columns": ["Ursprung", "Ansatz", "Funktion", "Innervation"],
  "rows": [
    {
      "question": "M. gluteus maximus",
      "answers": { "Ursprung": [...], "Ansatz": [...], ... }
    }
  ]
}
```

Einträge ohne Meta-Zeile haben kein `image`-Feld (wie bisher).

### Pipeline-Änderungen (`convert_text.py`)

**Architektur-Anpassung der Read-Funktionen:**
- `_read_excel()` und `_read_csv()` geben neu ein rohes `all_rows`-Tupel zurück (Typ: `list[tuple]`) statt des aufgeteilten `(headers, data_rows)`
- `main()` ruft danach `_extract_image_meta(all_rows)` auf → gibt `(image_meta, remaining_rows)` zurück
- Dann wird aus `remaining_rows` wie bisher `headers = remaining_rows[0]`, `data_rows = remaining_rows[1:]` abgeleitet

**Neue Funktion `_extract_image_meta(all_rows) -> (image_meta, remaining_rows)`:**
- Prüft ob erste Zeile `all_rows[0][0]` case-insensitiv `"BILD"` ist
- Falls ja:
  - B1 = `all_rows[0][1]` – muss ein nicht-leerer String mit `.`-Dateiendung sein
  - Wenn B1 ungültig (leer, kein `.`): Fehlermeldung + `sys.exit()` 
  - OG-Filename aus B1 extrahieren, Clean-Name ableiten: `og_stem + "-clean.jpg"`
  - Rückgabe: `({ "og": ..., "clean": ... }, all_rows[1:])`
- Falls nein: Rückgabe `(None, all_rows)`

**`_build_entry()`:** erhält optionalen `image`-Parameter (default `None`); setzt `image`-Feld wenn vorhanden.

**Clean-Ableitung:** `og_stem + "-clean.jpg"` (identisch mit process.py und Migration).

**Hinweis zur Validierung:** `convert_text.py` prüft **nicht**, ob die referenzierten Bilddateien tatsächlich existieren. Das ist Benutzerverantwortung. Das Quiz rendert das Bild nur, wenn es geladen werden kann (onerror-Handler blendet es aus).

### Frontend-Änderungen (`web/js/quiz.js`)

**Signaturen ändern** (konsistent mit `loadLernen`/`loadQuiz`, die ebenfalls Base-Paths übergeben bekommen):

```
loadTextLernen(entry, ogImgBase)   // war: loadTextLernen(entry)
loadTextQuiz(entry, imgBase)       // war: loadTextQuiz(entry)
```

**`app.js` Aufruf-Update** (die Aufrufstellen übergeben die bereits definierten Konstanten):
```js
loadTextLernen(entry, OG_IMG_BASE);   // war: loadTextLernen(entry)
loadTextQuiz(entry, IMG_BASE);         // war: loadTextQuiz(entry)
```

**Bild-Rendering in `loadTextLernen(entry, ogImgBase)`:**
```
_textWrapperSetup()
→ wenn entry.image:
    <img class="tq-quiz-image" src="{ogImgBase + entry.image.og}">
    img.onerror → img.style.display = 'none'
    textWrapper.appendChild(img)
→ dann: forEach rows → sections
```

**Bild-Rendering in `loadTextQuiz(entry, imgBase)`:**
```
_textWrapperSetup()
→ wenn entry.image:
    <img class="tq-quiz-image" src="{imgBase + entry.image.clean}">
    img.onerror → img.style.display = 'none'
    textWrapper.appendChild(img)
→ dann: forEach rows → sections
```

Das Bild-Element kommt **vor** den Frage-Sektionen, also ganz oben im `text-quiz-wrapper`.

### CSS-Änderungen (`web/css/style.css`)

Neue Klasse `.tq-quiz-image`:
```css
.tq-quiz-image {
    display: block;
    max-width: 100%;
    max-height: 40vh;
    margin: 0 auto 20px;
    border-radius: 4px;
    object-fit: contain;
}

@media (max-width: 600px) {
    .tq-quiz-image {
        max-height: 35vh;
    }
}
```

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `pipeline/migrate_images.py` | **Neu** – Migrations-Script |
| `pipeline/convert_text.py` | Meta-Zeile erkennen, `image`-Feld setzen |
| `web/js/quiz.js` | Bild in `loadTextLernen` und `loadTextQuiz` rendern |
| `web/css/style.css` | `.tq-quiz-image` Klasse |
| `web/data/data.json` | Durch Migration aktualisiert |
| `web/data/images/*.jpg` | Durch Migration umbenannt |

`process.py` und `export.py` bleiben unverändert (process.py erzeugt bereits den richtigen Namen).

---

## Nicht in diesem Scope

- Zoom/Pan für Bild im Text-Quiz (nur statische Anzeige)
- Bilder pro Zeile (nur ein Bild pro gesamtem Quiz-Eintrag)
- Sticky/fixiertes Bild beim Scrollen
