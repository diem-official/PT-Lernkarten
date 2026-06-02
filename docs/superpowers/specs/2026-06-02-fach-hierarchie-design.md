# Design: Fach-Hierarchie (4-stufiges Menü)

**Datum:** 2026-06-02  
**Status:** Genehmigt

## Zusammenfassung

Das Lernkarten-System erhält eine neue oberste Hierarchieebene **Fach**. Statt der bisherigen 3-stufigen Ansicht (Kategorie › Unterkategorie › Ansicht) gibt es künftig 4 Stufen: **Fach › Kategorie › Unterkategorie › Ansicht**. Alle bestehenden Inhalte gehören zum Fach „Anatomie 1".

---

## 1. Datei-Namenskonvention

### Alt
```
Kategorie-Unterkategorie-Ansicht.{jpg,png,xlsx,csv}
```

### Neu
```
Fach-Kategorie-Unterkategorie-Ansicht.{jpg,png,xlsx,csv}
```

Beispiel: `Anatomie 1-Bänder-Becken-Dorsal.png` → Menüeintrag **Anatomie 1 › Bänder › Becken › Dorsal**

---

## 2. JSON-Datenformat

### data.json (Image-Einträge)

Neues Feld `subject` (erstes inhaltliches Feld). `filename` und `og_filename` spiegeln den neuen Dateinamen wider.

```json
{
  "filename": "Anatomie 1-Bänder-Becken-Dorsal-clean.jpg",
  "og_filename": "Anatomie 1-Bänder-Becken-Dorsal.png",
  "subject": "Anatomie 1",
  "category": "Bänder",
  "subcategory": "Becken",
  "view": "Dorsal",
  "labels": [...]
}
```

### text-data.json (Text-Einträge)

Gleiches `subject`-Feld:

```json
{
  "type": "text",
  "subject": "Anatomie 1",
  "category": "Muskeln Detail",
  "subcategory": "Gesäß",
  "view": "Gluteus",
  "columns": [...],
  "rows": [...]
}
```

---

## 3. Pipeline-Änderungen

### pipeline/export.py

`build_entry` bekommt neuen Parameter `subject`:

```python
def build_entry(clean_filename, og_filename, labels, *, subject, category, subcategory, view):
    return {
        "filename": clean_filename,
        "og_filename": og_filename,
        "subject": subject,
        "category": category,
        "subcategory": subcategory,
        "view": view,
        "labels": labels,
    }
```

### pipeline/process.py

Vier Änderungen:

1. `NAME_RE` erwartet 4-teiligen Namen:
   ```python
   NAME_RE = re.compile(r'^[^-]+-[^-]+-[^-]+-[^-]+\.\w+$')
   ```
   Außerdem den SKIP-Log-String auf Zeile 159 aktualisieren: `"does not match Fach-Kategorie-Unterkategorie-Ansicht.ext"`

2. `_parse_stem` gibt 4-Tupel zurück:
   ```python
   def _parse_stem(stem: str) -> tuple[str, str, str, str]:
       parts = stem.split('-', 3)
       return parts[0], parts[1], parts[2], parts[3]
   ```

3. `build_entry`-Aufruf übergibt `subject`:
   ```python
   fach, category, subcategory, view = _parse_stem(path.stem)
   # ...
   entries.append(build_entry(
       clean_name, og_name, labels,
       subject=fach, category=category,
       subcategory=subcategory, view=view,
   ))
   ```

### pipeline/convert_text.py

Drei Änderungen:

1. `_parse_stem` splittet auf 4 Teile:
   ```python
   def _parse_stem(stem):
       parts = stem.split('-', 3)
       if len(parts) < 4:
           return None
       return {
           'subject':     parts[0].strip(),
           'category':    parts[1].strip(),
           'subcategory': parts[2].strip(),
           'view':        parts[3].strip(),
       }
   ```

2. `_build_entry` nimmt `subject` auf:
   ```python
   return {
       'type':        'text',
       'subject':     meta['subject'],
       'category':    meta['category'],
       'subcategory': meta['subcategory'],
       'view':        meta['view'],
       'columns':     columns,
       'rows':        rows,
   }
   ```

3. Deduplizierungs-Key um `subject` erweitert:
   ```python
   key = (entry['subject'], entry['category'], entry['subcategory'], entry['view'])
   ```

---

## 4. Web-Frontend

### web/js/menu.js

**Menübaum-Struktur:**
```js
// Neu: { Fach: { Kategorie: { Unterkategorie: [{ansicht, entry}] } } }
var tree = {};
```

**Vereinfachung:** Da alle JSON-Einträge (Bild + Text) nun `subject`, `category`, `subcategory`, `view` direkt als Felder besitzen, entfällt das Filename-Parsing für Image-Einträge. Beide Typen werden gleich behandelt:

```js
data.forEach(function (entry) {
    var fach    = entry.subject;
    var kat     = entry.category;
    var unter   = entry.subcategory;
    var ansicht = entry.view;
    // tree aufbauen ...
});
```

**DOM-Struktur** (neue oberste Ebene):
- CSS-Klassen: `menu-fach`, `menu-fach-btn`, `menu-fach-list`
- Darunter unverändert: `menu-kat`, `menu-unter`, `menu-ansicht-li`

### web/js/app.js

Beide Pfade (Text-Entry und Image-Entry) nutzen die stored Felder statt Filename-Parsing:

```js
// Text-Entry (war: entry.view + ' – ' + entry.subcategory)
mobileTitle.textContent = entry.subject + ' – ' + entry.subcategory + ' – ' + entry.view;

// Image-Entry (war: rawName aus Filename-Parsing)
mobileTitle.textContent = entry.subject + ' – ' + entry.subcategory + ' – ' + entry.view;
```

Der bisherige Filename-Parsing-Block (`rawName`) in app.js wird entfernt; stattdessen einheitlich `entry.subject/subcategory/view`.

### web/js/quiz.js

Keine Änderungen erforderlich — `quiz.js` rendert den Quiz-Inhalt und greift nur auf `entry.columns`, `entry.rows`, `entry.labels` zu, nicht auf die Hierarchiefelder.

---

## 5. Migration (einmalig)

Ein Python-Skript `pipeline/migrate_to_fach.py` führt drei Schritte aus. Default-Fach für alle bestehenden Einträge: **„Anatomie 1"**.

**Schritt 1 – Input/-Dateien umbenennen** (23 Dateien):
```
Bänder-Becken-Dorsal.png  →  Anatomie 1-Bänder-Becken-Dorsal.png
```

**Schritt 2 – Tabellen/-Dateien umbenennen** (1 Datei):
```
Muskeln Detail-Gesäß-Gluteus.xlsx  →  Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx
```

**Schritt 3 – JSON-Dateien aktualisieren:**
- `subject: "Anatomie 1"` zu allen Einträgen in `data.json` und `text-data.json` hinzufügen
- `filename` und `og_filename` in `data.json` mit dem neuen Präfix „Anatomie 1-" versehen (z.B. `og_filename: "Anatomie 1-Bänder-Becken-Dorsal.png"`)

**Reihenfolge der Ausführung:** Migration läuft vor allen Code-Änderungen an den Pipeline-Scripts. Nach der Migration sind `data.json`-Einträge mit korrekten `og_filename`-Werten versehen, sodass `process.py` sie beim nächsten Lauf via `processed_stems` korrekt als bereits verarbeitet erkennt.

**Die Bilder in `web/data/images/` und `web/data/og-images/`** behalten ihre bisherigen 3-teiligen Dateinamen (z.B. `Bänder-Becken-Dorsal-clean.jpg`). Das ist möglich, weil `menu.js` nach der Überarbeitung nur noch die stored Felder `entry.filename` aus `data.json` nutzt — und dieser Wert wird in Schritt 3 mit dem neuen Präfix versehen. Die physischen Bilddateien müssen nicht umbenannt werden.

---

## 6. Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `pipeline/export.py` | Parameter `subject` hinzufügen |
| `pipeline/process.py` | `NAME_RE`, `_parse_stem`, `build_entry`-Aufruf |
| `pipeline/convert_text.py` | `_parse_stem`, `_build_entry`, Deduplizierungs-Key |
| `pipeline/migrate_to_fach.py` | Neues Migrations-Script |
| `web/js/menu.js` | 4. Menü-Ebene, Filename-Parsing entfernen |
| `web/js/app.js` | `mobileTitle` (beide Pfade auf stored Felder umstellen, Filename-Parsing entfernen) |
| `web/js/quiz.js` | Keine Änderung (greift nur auf `labels`/`rows`/`columns` zu) |
| `web/data/data.json` | `subject`-Feld + Dateinamen (Migration) |
| `web/data/text-data.json` | `subject`-Feld (Migration) |
| `web/css/style.css` | CSS für `menu-fach`-Klassen |
| `README.md` | Namenskonvention aktualisieren |
| `Input/*.png` | Umbenennung (Migration) |
| `Tabellen/*.xlsx` | Umbenennung (Migration) |
