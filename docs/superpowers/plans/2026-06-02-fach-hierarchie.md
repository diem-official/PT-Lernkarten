# Fach-Hierarchie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Erweitere das 3-stufige Menü (Kategorie › Unterkategorie › Ansicht) um eine neue oberste Ebene „Fach", sodass die vollständige Hierarchie Fach › Kategorie › Unterkategorie › Ansicht lautet. Alle bestehenden Inhalte gehören zum Fach „Anatomie 1".

**Architecture:** Dateinamen bekommen ein neues führendes Segment (`Fach-Kategorie-Unterkategorie-Ansicht`). Beide JSON-Dateien (`data.json`, `text-data.json`) erhalten ein neues Feld `subject`. Ein einmaliges Migrationsskript benennt Quell- und og-image-Dateien um und aktualisiert die JSONs. Das Frontend-Menü bekommt eine vierte Accordion-Ebene; der bisherige Filename-Parsing-Code in `menu.js` und `app.js` wird durch direkten Feldzugriff ersetzt.

**Tech Stack:** Python 3.10+, Vanilla JS (ES5), HTML/CSS — kein Build-Schritt.

---

## Datei-Übersicht

| Datei | Rolle |
|---|---|
| `pipeline/export.py` | `build_entry` — fügt `subject`-Parameter hinzu |
| `pipeline/process.py` | Bild-Pipeline — `NAME_RE`, `_parse_stem`, Unpacking, `build_entry`-Aufruf |
| `pipeline/convert_text.py` | Text-Pipeline — `_parse_stem`, `_build_entry`, Deduplizierungs-Key |
| `pipeline/migrate_to_fach.py` | Neues einmaliges Migrationsskript |
| `pipeline/tests/test_export.py` | Tests für `build_entry` — `subject` ergänzen |
| `pipeline/tests/test_process.py` | Tests für `_parse_stem` — auf 4-Tupel umstellen |
| `web/js/menu.js` | Menü — 4. Accordion-Ebene, Filename-Parsing entfernen |
| `web/js/app.js` | App — `mobileTitle`, `rawName`-Block entfernen |
| `web/css/style.css` | Styles für neue `menu-fach`-Klassen |
| `README.md` | Namenskonvention aktualisieren |

---

## Task 1: Tests für `export.py` updaten (TDD — zuerst rot machen)

**Files:**
- Modify: `pipeline/tests/test_export.py:14-21`, `36-43`, `51-60`

Die drei bestehenden Tests übergeben kein `subject` an `build_entry`. Das wird nach der Implementierung einen `TypeError` werfen. Wir stellen sie jetzt auf das neue Interface um, damit sie nach der nächsten Aufgabe grün werden.

- [ ] **Step 1: Tests anpassen**

Ändere die drei `build_entry`-Aufrufe und füge jeweils `subject="Anatomie 1"` hinzu. Füge außerdem in `test_build_entry_includes_metadata` die Assertion `assert entry["subject"] == "Anatomie 1"` hinzu:

```python
# test_build_entry_includes_metadata (Zeilen 14–26):
entry = build_entry(
    "Knochen-Becken-dorsal-clean.jpg",
    "Knochen-Becken-dorsal.jpg",
    labels,
    subject="Anatomie 1",
    category="Knochen",
    subcategory="Becken",
    view="dorsal",
)
assert entry["subject"] == "Anatomie 1"
assert entry["filename"] == "Knochen-Becken-dorsal-clean.jpg"
# (restliche Assertions bleiben)

# test_build_entry_labels_passthrough (Zeilen 36–43):
entry = build_entry(
    "test-clean.jpg",
    "test.jpg",
    labels,
    subject="Anatomie 1",
    category="Knochen",
    subcategory="Becken",
    view="ventral",
)

# test_build_entry_empty_labels (Zeilen 51–60):
entry = build_entry(
    "test-clean.jpg",
    "test.jpg",
    [],
    subject="Anatomie 1",
    category="Muskeln",
    subcategory="Arm",
    view="frontal",
)
```

- [ ] **Step 2: Tests laufen lassen — sie müssen FEHLSCHLAGEN**

```bash
cd "/home/diem/PT Lernkarten/pipeline" && python -m pytest tests/test_export.py -v
```

Erwartetes Ergebnis: `TypeError: build_entry() got an unexpected keyword argument 'subject'`

---

## Task 2: `export.py` — `subject`-Parameter hinzufügen

**Files:**
- Modify: `pipeline/export.py:6-21`

- [ ] **Step 1: `build_entry` anpassen**

```python
def build_entry(
    clean_filename: str,
    og_filename: str,
    labels: list,
    *,
    subject: str,
    category: str,
    subcategory: str,
    view: str,
) -> dict:
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

- [ ] **Step 2: Tests grün**

```bash
cd "/home/diem/PT Lernkarten/pipeline" && python -m pytest tests/test_export.py -v
```

Erwartetes Ergebnis: alle Tests PASS.

- [ ] **Step 3: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/export.py pipeline/tests/test_export.py
git commit -m "feat: add subject field to build_entry"
```

---

## Task 3: Tests für `process.py` updaten (TDD — zuerst rot machen)

**Files:**
- Modify: `pipeline/tests/test_process.py:18-29`

- [ ] **Step 1: Die drei `_parse_stem`-Tests auf 4-Tupel umstellen**

```python
def test_parse_stem_simple():
    assert _parse_stem("Anatomie 1-Knochen-Becken-dorsal") == ("Anatomie 1", "Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Anatomie 1-Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Anatomie 1", "Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Anatomie 1-Muskeln-Arm-lateral links") == ("Anatomie 1", "Muskeln", "Arm", "lateral links")
```

- [ ] **Step 2: Tests laufen lassen — sie müssen FEHLSCHLAGEN**

```bash
cd "/home/diem/PT Lernkarten/pipeline" && python -m pytest tests/test_process.py::test_parse_stem_simple tests/test_process.py::test_parse_stem_complex_subcategory tests/test_process.py::test_parse_stem_view_with_spaces -v
```

Erwartetes Ergebnis: FAIL (zu wenige Rückgabewerte zum Entpacken).

---

## Task 4: `process.py` — 5 Änderungen

**Files:**
- Modify: `pipeline/process.py:29`, `pipeline/process.py:37-40`, `pipeline/process.py:159`, `pipeline/process.py:212`, `pipeline/process.py:258-265`

- [ ] **Step 1: `NAME_RE` auf 4 Segmente (Zeile 29)**

```python
NAME_RE = re.compile(r'^[^-]+-[^-]+-[^-]+-[^-]+\.\w+$')
```

- [ ] **Step 2: `_parse_stem` auf 4-Tupel (Zeilen 37–40)**

```python
def _parse_stem(stem: str) -> tuple[str, str, str, str]:
    """Split 'Fach-Category-Subcategory-View' filename stem into four metadata parts."""
    parts = stem.split('-', 3)
    return parts[0], parts[1], parts[2], parts[3]
```

- [ ] **Step 3: SKIP-Log-String (Zeile 159) aktualisieren**

```python
print(f"  SKIP {path.name} – does not match Fach-Kategorie-Unterkategorie-Ansicht.ext")
```

- [ ] **Step 4: Unpacking auf 4 Variablen (Zeile 212)**

```python
fach, category, subcategory, view = _parse_stem(path.stem)
```

- [ ] **Step 5: `build_entry`-Aufruf mit `subject` (Zeilen 258–265)**

```python
entries.append(build_entry(
    clean_name,
    og_name,
    labels,
    subject=fach,
    category=category,
    subcategory=subcategory,
    view=view,
))
```

- [ ] **Step 6: Tests grün**

```bash
cd "/home/diem/PT Lernkarten/pipeline" && python -m pytest tests/test_process.py -v
```

Erwartetes Ergebnis: alle Tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/process.py pipeline/tests/test_process.py
git commit -m "feat: extend process.py pipeline to 4-part filename (Fach-Kat-Unter-Ansicht)"
```

---

## Task 5: `convert_text.py` — 3 Änderungen

**Files:**
- Modify: `pipeline/convert_text.py:21-29`, `pipeline/convert_text.py:86-93`, `pipeline/convert_text.py:152`

Kein eigener Test-File für convert_text — wir verifizieren mit einem kurzen Smoke-Test am Ende.

- [ ] **Step 1: `_parse_stem` auf 4 Teile (Zeilen 21–29)**

```python
def _parse_stem(stem):
    """Split 'Fach-Kategorie-Unterkategorie-Ansicht' into a dict (max 3 splits)."""
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

- [ ] **Step 2: `_build_entry` mit `subject` (Zeilen 86–93)**

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

- [ ] **Step 3: Deduplizierungs-Key auf 4-Tupel (Zeile 152)**

```python
key = (entry['subject'], entry['category'], entry['subcategory'], entry['view'])
```

- [ ] **Step 4: Fehlermeldung aktualisieren (Zeile 119–121)**

```python
sys.exit(
    f'Dateiname "{stem}" folgt nicht dem Format Fach-Kategorie-Unterkategorie-Ansicht\n'
    f'Beispiel: "Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx"'
)
```

- [ ] **Step 5: Smoke-Test — convert_text mit einer Testdatei**

Erstelle eine temporäre CSV und prüfe die Ausgabe:

```bash
echo -e "Muskel;Ursprung\nGluteus maximus;Os ilium" > /tmp/test_fach.csv
mv /tmp/test_fach.csv "/tmp/Anatomie 1-Muskeln-Gesäß-Test.csv"
cd "/home/diem/PT Lernkarten"
python pipeline/convert_text.py "/tmp/Anatomie 1-Muskeln-Gesäß-Test.csv" --output /tmp/test-output.json
cat /tmp/test-output.json
```

Erwartetes Ergebnis: JSON mit `"subject": "Anatomie 1"`, `"category": "Muskeln"`, `"subcategory": "Gesäß"`, `"view": "Test"`.

- [ ] **Step 6: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/convert_text.py
git commit -m "feat: extend convert_text.py to 4-part filename with subject field"
```

---

## Task 6: Migrationsskript `migrate_to_fach.py` schreiben

**Files:**
- Create: `pipeline/migrate_to_fach.py`

Das Skript führt die einmalige Datenmigration durch. Es ist idempotent — bei erneutem Aufruf ändert es nichts, was bereits migriert wurde.

**Reihenfolge:** Diesen Task und Task 7–8 (Frontend) vollständig abschließen und committen, BEVOR das Skript ausgeführt wird.

- [ ] **Step 1: Skript schreiben**

```python
#!/usr/bin/env python3
"""
Einmalige Migration: 3-teilige → 4-teilige Dateinamen (Fach-Präfix).

Schritte:
  1. Input/-Dateien umbenennen (Präfix „Anatomie 1-")
  2. Tabellen/-Dateien umbenennen
  3. web/data/og-images/-Dateien umbenennen
  4. web/data/data.json aktualisieren: subject hinzufügen, og_filename updaten
  5. web/data/text-data.json aktualisieren: subject hinzufügen

WICHTIG: web/data/images/ (Clean-Images) wird NICHT angefasst.
         Die filename-Felder in data.json bleiben unverändert.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INPUT_DIR   = ROOT / 'Input'
TABELLEN_DIR = ROOT / 'Tabellen'
OG_IMAGES_DIR = ROOT / 'web' / 'data' / 'og-images'
DATA_JSON    = ROOT / 'web' / 'data' / 'data.json'
TEXT_JSON    = ROOT / 'web' / 'data' / 'text-data.json'
DEFAULT_FACH = 'Anatomie 1'
PREFIX       = DEFAULT_FACH + '-'

SUPPORTED_IMG = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
SUPPORTED_TBL = {'.xlsx', '.csv'}


def _needs_prefix(name: str) -> bool:
    return not name.startswith(PREFIX)


def _rename_files(directory: Path, extensions: set) -> int:
    count = 0
    if not directory.is_dir():
        print(f"  SKIP {directory} — nicht gefunden")
        return 0
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in extensions:
            continue
        if _needs_prefix(path.name):
            new_path = path.parent / (PREFIX + path.name)
            path.rename(new_path)
            print(f"  {path.name}  →  {new_path.name}")
            count += 1
        else:
            print(f"  SKIP (bereits migriert): {path.name}")
    return count


def _migrate_data_json(path: Path) -> None:
    if not path.exists():
        print(f"  SKIP {path} — nicht gefunden")
        return
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)
    changed = 0
    for entry in entries:
        if 'subject' not in entry:
            entry['subject'] = DEFAULT_FACH
            changed += 1
        og = entry.get('og_filename', '')
        if og and _needs_prefix(og):
            entry['og_filename'] = PREFIX + og
            changed += 1
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"  {path.name}: {changed} Felder aktualisiert ({len(entries)} Einträge)")


def _migrate_text_json(path: Path) -> None:
    if not path.exists():
        print(f"  SKIP {path} — nicht gefunden")
        return
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)
    changed = 0
    for entry in entries:
        if 'subject' not in entry:
            entry['subject'] = DEFAULT_FACH
            changed += 1
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"  {path.name}: {changed} Felder aktualisiert ({len(entries)} Einträge)")


def main():
    print(f"\n=== Migration zu Fach-Hierarchie (Fach: '{DEFAULT_FACH}') ===\n")

    print("Schritt 1: Input/-Dateien umbenennen")
    n = _rename_files(INPUT_DIR, SUPPORTED_IMG)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 2: Tabellen/-Dateien umbenennen")
    n = _rename_files(TABELLEN_DIR, SUPPORTED_TBL)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 3: og-images/-Dateien umbenennen")
    n = _rename_files(OG_IMAGES_DIR, SUPPORTED_IMG)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 4: data.json aktualisieren")
    _migrate_data_json(DATA_JSON)
    print()

    print("Schritt 5: text-data.json aktualisieren")
    _migrate_text_json(TEXT_JSON)
    print()

    print("=== Migration abgeschlossen ===")
    print("HINWEIS: web/data/images/ wurde NICHT angefasst (Clean-Images bleiben unverändert).")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Syntax prüfen**

```bash
cd "/home/diem/PT Lernkarten"
python -m py_compile pipeline/migrate_to_fach.py && echo "OK"
```

Erwartetes Ergebnis: `OK` (kein Syntaxfehler).

- [ ] **Step 3: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/migrate_to_fach.py
git commit -m "feat: add migrate_to_fach.py migration script"
```

---

## Task 7: `web/css/style.css` — neue Fach-Ebene stylen

**Files:**
- Modify: `web/css/style.css` — nach dem Kommentar `/* Level 1: Kategorie */` neue Regeln einfügen

Die neue `menu-fach`-Ebene sitzt über `menu-kat`. Sie bekommt dieselbe Basisstruktur wie `menu-kat > button`, ist aber optisch deutlicher hervorgehoben (größere Schrift, leicht farbiger Hintergrund).

- [ ] **Step 1: CSS-Regeln einfügen** (direkt VOR `/* Level 1: Kategorie */`):

```css
/* Level 0: Fach (oberste Ebene) */
.menu-fach > button {
    width: 100%;
    text-align: left;
    background: #e6eaf2;
    border: none;
    border-bottom: 1px solid #c0c8d8;
    cursor: pointer;
    padding: 10px 16px;
    font-size: 16px;
    font-weight: 800;
    color: #1a2a4a;
    display: flex;
    align-items: center;
    gap: 6px;
}

.menu-fach > button::before {
    content: '▶';
    font-size: 10px;
    transition: transform 0.15s;
    display: inline-block;
}

.menu-fach > button.expanded::before {
    transform: rotate(90deg);
}

.menu-fach > button:hover {
    background: #d4daea;
}

.menu-fach-list {
    list-style: none;
}
```

- [ ] **Step 2: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add web/css/style.css
git commit -m "style: add menu-fach CSS level for new top-level hierarchy"
```

---

## Task 8: `web/js/menu.js` — 4. Accordion-Ebene

**Files:**
- Modify: `web/js/menu.js` (vollständige Neufassung der Funktion)

Der Menübaum ändert sich von `{ Kat: { Unter: [...] } }` zu `{ Fach: { Kat: { Unter: [...] } } }`. Das Filename-Parsing für Image-Entries entfällt, weil `data.json` jetzt alle Felder direkt enthält.

- [ ] **Step 1: `buildMenu` vollständig ersetzen**

```js
/**
 * buildMenu(data, onSelect)
 *   data     – combined array from data.json + text-data.json
 *   onSelect – function(entry, mode) called when user clicks an Ansicht
 *
 * All entries must have: subject, category, subcategory, view fields.
 */
function buildMenu(data, onSelect) {
    var root    = document.getElementById('menu-root');
    var loading = document.getElementById('menu-loading');

    // Build tree: { Fach: { Kategorie: { Unterkategorie: [{ansicht, entry}] } } }
    var tree = {};
    data.forEach(function (entry) {
        var fach    = entry.subject;
        var kat     = entry.category;
        var unter   = entry.subcategory;
        var ansicht = entry.view;

        if (!fach || !kat || !unter || !ansicht) return;

        if (!tree[fach])             tree[fach]             = {};
        if (!tree[fach][kat])        tree[fach][kat]        = {};
        if (!tree[fach][kat][unter]) tree[fach][kat][unter] = [];
        tree[fach][kat][unter].push({ ansicht: ansicht, entry: entry });
    });

    // DOM builder helpers
    function makeBtn(className, text) {
        var btn = document.createElement('button');
        btn.className   = className;
        btn.textContent = text;
        return btn;
    }

    function toggleList(list, btn) {
        var hidden = list.classList.toggle('hidden');
        if (hidden) {
            btn.classList.remove('expanded');
        } else {
            btn.classList.add('expanded');
        }
    }

    Object.keys(tree).sort().forEach(function (fach) {
        var fachLi  = document.createElement('li');
        fachLi.className = 'menu-fach';

        var fachBtn = makeBtn('menu-fach-btn', fach);

        var katList = document.createElement('ul');
        katList.className = 'menu-fach-list hidden';

        fachBtn.addEventListener('click', function () {
            toggleList(katList, fachBtn);
        });

        Object.keys(tree[fach]).sort().forEach(function (kat) {
            var katLi  = document.createElement('li');
            katLi.className = 'menu-kat';

            var katBtn = makeBtn('menu-kat-btn', kat);

            var unterList = document.createElement('ul');
            unterList.className = 'menu-unter-list hidden';

            katBtn.addEventListener('click', function () {
                toggleList(unterList, katBtn);
            });

            Object.keys(tree[fach][kat]).sort().forEach(function (unter) {
                var unterLi = document.createElement('li');
                unterLi.className = 'menu-unter';

                var unterBtn = makeBtn('menu-unter-btn', unter);

                var ansichtList = document.createElement('ul');
                ansichtList.className = 'menu-ansicht-list hidden';

                unterBtn.addEventListener('click', function () {
                    toggleList(ansichtList, unterBtn);
                });

                tree[fach][kat][unter].forEach(function (item) {
                    var ansichtLi = document.createElement('li');
                    ansichtLi.className = 'menu-ansicht-li';

                    var label     = item.entry.type === 'text'
                        ? item.ansicht + ' ✒'
                        : item.ansicht;
                    var testenBtn = makeBtn('menu-ansicht-btn', label);

                    function setActive() {
                        document.querySelectorAll('.menu-ansicht-li.active').forEach(function (li) {
                            li.classList.remove('active');
                        });
                        ansichtLi.classList.add('active');
                    }

                    testenBtn.addEventListener('click', function () {
                        setActive();
                        onSelect(item.entry, 'testen');
                    });

                    ansichtLi.appendChild(testenBtn);

                    if (item.entry.type !== 'text') {
                        var lernenBtn = makeBtn('menu-lernen-btn', 'Lernen');
                        lernenBtn.addEventListener('click', function () {
                            setActive();
                            onSelect(item.entry, 'lernen');
                        });
                        ansichtLi.appendChild(lernenBtn);
                    }

                    ansichtList.appendChild(ansichtLi);
                });

                unterLi.appendChild(unterBtn);
                unterLi.appendChild(ansichtList);
                unterList.appendChild(unterLi);
            });

            katLi.appendChild(katBtn);
            katLi.appendChild(unterList);
            katList.appendChild(katLi);
        });

        fachLi.appendChild(fachBtn);
        fachLi.appendChild(katList);
        root.appendChild(fachLi);
    });

    loading.classList.add('hidden');
    root.classList.remove('hidden');
}
```

- [ ] **Step 2: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add web/js/menu.js
git commit -m "feat: extend menu.js to 4-level accordion (Fach › Kat › Unter › Ansicht)"
```

---

## Task 9: `web/js/app.js` — mobileTitle und rawName-Block bereinigen

**Files:**
- Modify: `web/js/app.js:68-83`

Der bestehende Code baut `mobileTitle` für Text-Entries aus `entry.view + ' – ' + entry.subcategory` und für Image-Entries aus einem `rawName`-String-Parsing des Dateinamens. Beides wird auf direkte Feldnutzung umgestellt.

- [ ] **Step 1: Den `onSelect`-Callback in app.js anpassen**

Ersetze den gesamten Block innerhalb des `buildMenu`-Callbacks (Zeilen 68–84 ungefähr) durch:

```js
buildMenu(allData, function (entry, mode) {
    closeDrawer();
    mobileTitle.textContent = entry.subject + ' – ' + entry.subcategory + ' – ' + entry.view;

    if (entry.type === 'text') {
        loadTextQuiz(entry);
    } else {
        if (mode === 'lernen') {
            loadLernen(entry, OG_IMG_BASE);
        } else {
            loadQuiz(entry, IMG_BASE);
        }
    }
});
```

(Der alte `rawName`-Block und die separate Text/Image-Weiche für `mobileTitle` entfallen komplett.)

- [ ] **Step 2: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add web/js/app.js
git commit -m "refactor: simplify app.js mobileTitle using stored entry fields"
```

---

## Task 10: Migration ausführen

**Voraussetzung:** Tasks 1–9 sind committed. Alle Code-Änderungen sind aktiv, bevor die Daten migriert werden.

- [ ] **Step 1: Dry-run — prüfen, welche Dateien umbenannt werden**

```bash
ls "/home/diem/PT Lernkarten/Input/" | head -5
ls "/home/diem/PT Lernkarten/web/data/og-images/" | head -5
```

Stelle sicher, dass die Dateien noch die alten 3-teiligen Namen haben.

- [ ] **Step 2: Migration ausführen**

```bash
cd "/home/diem/PT Lernkarten"
python pipeline/migrate_to_fach.py
```

Erwartetes Ergebnis:
```
=== Migration zu Fach-Hierarchie (Fach: 'Anatomie 1') ===

Schritt 1: Input/-Dateien umbenennen
  Bänder-Becken-Dorsal.png  →  Anatomie 1-Bänder-Becken-Dorsal.png
  ...
  → 23 Dateien umbenannt

Schritt 2: Tabellen/-Dateien umbenennen
  → 1 Dateien umbenannt

Schritt 3: og-images/-Dateien umbenennen
  → 24 Dateien umbenannt

Schritt 4: data.json aktualisieren
  data.json: N Felder aktualisiert (23 Einträge)

Schritt 5: text-data.json aktualisieren
  text-data.json: 1 Felder aktualisiert (1 Einträge)

=== Migration abgeschlossen ===
```

- [ ] **Step 3: Ergebnis verifizieren**

```bash
# Prüfen ob subject-Feld in data.json vorhanden
python3 -c "
import json
with open('web/data/data.json') as f:
    d = json.load(f)
print('data.json Einträge:', len(d))
print('Fehlende subject-Felder:', sum(1 for e in d if 'subject' not in e))
print('Beispiel og_filename:', d[0]['og_filename'])
print('Beispiel filename:', d[0]['filename'])
with open('web/data/text-data.json') as f:
    t = json.load(f)
print('text-data.json subject:', t[0].get('subject'))
"
```

Erwartetes Ergebnis: 0 fehlende subject-Felder, `og_filename` beginnt mit „Anatomie 1-", `filename` ist unverändert (kein Präfix).

- [ ] **Step 4: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add web/data/data.json web/data/text-data.json
git add "Input/" "Tabellen/"
git commit -m "data: migrate all entries to Fach-Hierarchie (Anatomie 1)"
```

---

## Task 11: Web-App manuell testen

**Files:**  (keine Codeänderungen in diesem Task)

- [ ] **Step 1: Lokalen Server starten**

```bash
cd "/home/diem/PT Lernkarten/web"
python3 -m http.server 8080
```

Öffne http://localhost:8080 im Browser.

- [ ] **Step 2: Menü prüfen**

- Das Menü zeigt jetzt **„Anatomie 1"** als oberste, klappbare Ebene
- Darunter erscheinen die bekannten Kategorien (Bänder, Knochen, …)
- Tiefere Ebenen (Unterkategorie, Ansicht) funktionieren wie zuvor

- [ ] **Step 3: Quiz testen (Testen-Modus)**

- Klicke auf einen Ansicht-Eintrag → Quiz lädt und Bild erscheint korrekt
- Mobile Title zeigt: „Anatomie 1 – [Unterkategorie] – [Ansicht]"

- [ ] **Step 4: Lernen-Modus testen**

- Klicke „Lernen" bei einem Bildeintrag → Originalbild lädt ohne 404

- [ ] **Step 5: Text-Quiz testen**

- Klicke auf einen ✒-Eintrag → Text-Quiz erscheint korrekt

---

## Task 12: README aktualisieren

**Files:**
- Modify: `README.md:46-48`, `README.md:88-90`

- [ ] **Step 1: Namenskonvention in Phase 1a updaten**

```markdown
### File naming convention

```
Fach-Kategorie-Unterkategorie-Ansicht.{jpg,jpeg,png,tif,tiff}
```

Example: `Anatomie 1-Knochen-Arm-dorsal.jpg` → menu entry **Anatomie 1 › Knochen › Arm › dorsal**
```

- [ ] **Step 2: Namenskonvention in Phase 1b updaten**

```markdown
### File naming convention (same as images)

```
Fach-Kategorie-Unterkategorie-Ansicht.{xlsx,csv}
```

Example: `Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx` → menu entry **Anatomie 1 › Muskeln Detail › Gesäß › Gluteus**
```

- [ ] **Step 3: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add README.md
git commit -m "docs: update README file naming convention to 4-part Fach-Kat-Unter-Ansicht"
```

---

## Fertig

Alle 12 Tasks abgeschlossen. Das System unterstützt jetzt die 4-stufige Hierarchie Fach › Kategorie › Unterkategorie › Ansicht. Neue Inhalte werden mit dem Präfix `Fach-` benannt, z.B. `Anatomie 2-Knochen-Arm-dorsal.jpg`.
