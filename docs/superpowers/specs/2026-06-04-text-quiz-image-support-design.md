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

1. Liest `web/data/data.json`
2. Für jeden Eintrag berechnet es den neuen Clean-Namen: `og_stem + "-clean.jpg"`
3. Wenn `old_filename != new_filename`:
   - Benennt `web/data/images/<old>.jpg` → `web/data/images/<new>.jpg` um
   - Aktualisiert `filename` im Eintrag
4. Schreibt die aktualisierte `data.json` zurück

**Fehlerbehandlung:** Wenn eine Datei nicht gefunden wird, Warnung ausgeben und fortfahren (nicht abbrechen).

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
  "rows": [...]
}
```

Einträge ohne Meta-Zeile haben kein `image`-Feld (wie bisher).

### Pipeline-Änderungen (`convert_text.py`)

- `_read_excel()` und `_read_csv()`: Rückgabe bleibt `(headers, data_rows)` – **keine Änderung**
- Neue Funktion `_extract_image_meta(all_rows)`:
  - Prüft ob erste Zeile A1 == `"BILD"` (case-insensitive)
  - Falls ja: extrahiert OG-Filename aus B1, leitet Clean-Name ab, gibt `{ "og": ..., "clean": ... }` zurück – und entfernt diese Zeile aus `all_rows`
  - Falls nein: gibt `None` zurück
- `_build_entry()`: erhält optionalen `image`-Parameter; setzt `image`-Feld wenn vorhanden
- Clean-Ableitung: `og_stem + "-clean.jpg"` (identisch mit process.py und Migration)

### Frontend-Änderungen (`web/js/quiz.js`)

In `loadTextLernen(entry)`:
```
_textWrapperSetup()
→ wenn entry.image: <img class="tq-quiz-image" src="OG_IMG_BASE + entry.image.og"> einfügen
→ dann: forEach rows → sections
```

In `loadTextQuiz(entry)`:
```
_textWrapperSetup()
→ wenn entry.image: <img class="tq-quiz-image" src="IMG_BASE + entry.image.clean"> einfügen
→ dann: forEach rows → sections
```

Das Bild-Element kommt **vor** den Frage-Sektionen, also ganz oben im `text-quiz-wrapper`.

**Fehlerbehandlung:** `img.onerror` → Bild-Element ausblenden (kein fehlendes-Bild-Icon).

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
