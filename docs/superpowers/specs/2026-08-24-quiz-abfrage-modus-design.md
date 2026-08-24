# Design: Neuer Quiz-Abfrage-Modus für Bild-Ansichten

**Datum:** 2026-08-24
**Status:** Freigegeben

---

## Ziel

Ergänzung einer dritten Kategorie **Quiz** neben den bestehenden Modi **Lernen** und **Schreiben** für Bild-Ansichten. Im Gegensatz zum Schreiben-Modus (alle Nummern gleichzeitig, Freitext-Eingabe pro Feld) fragt der Quiz-Modus die Nummern **einzeln nacheinander** ab, mit Selbsteinschätzung (Korrekt/Falsch) statt Texteingabe-Validierung. Falsch beantwortete Nummern werden ans Ende der Abfrage-Warteschlange gehängt und später erneut gestellt, bis alle korrekt eingeschätzt wurden.

**Scope:** Nur Bild-Einträge (`data.json`, `entry.type !== 'text'`). Text-Einträge (Excel/CSV-basiert, `text-data.json`) sind **nicht** betroffen und behalten ihre bisherigen 2 Modi (Lernen, Schreiben).

---

## 1. Menü-Struktur

Pro Ansicht-Eintrag (Bild-Typ) entsteht ein zweizeiliger Block statt der bisherigen einzeiligen Button-Reihe:

- **Zeile 1:** reines Text-Label mit dem Ansicht-Namen (z. B. "Dorsal") — nicht klickbar, dient nur der Erkennbarkeit im Menü. Gleiche Einrückung/Optik wie der bisherige Ansicht-Button.
- **Zeile 2:** drei Buttons nebeneinander, in dieser Reihenfolge: **Lernen**, **Schreiben**, **Quiz**.
  - "Lernen" löst wie bisher `onSelect(entry, 'lernen')` aus.
  - "Schreiben" ersetzt den bisherigen Ansicht-Namen-Button; löst weiterhin denselben Modus aus wie bisher (`onSelect(entry, 'schreiben')` — Mode-String wird von `'testen'` auf `'schreiben'` umbenannt).
  - "Quiz" ist neu: `onSelect(entry, 'quiz')`.

Text-Einträge (✒) behalten die bisherige Struktur (Ansicht-Name klickbar löst Schreiben-Modus aus + separater Lernen-Button) unverändert bei, da für sie kein Quiz-Modus existiert.

---

## 2. Routing (`js/app.js`)

Der bestehende `onSelect`-Callback erweitert seine Verzweigung für Bild-Einträge um den neuen Modus:

```js
if (entry.type === 'text') {
    // unverändert: 'lernen' → loadTextLernen, sonst → loadTextQuiz
} else {
    if (mode === 'lernen')       loadLernen(entry, OG_IMG_BASE);
    else if (mode === 'quiz')    loadQuizAbfrage(entry, IMG_BASE);
    else                         loadQuiz(entry, IMG_BASE); // 'schreiben'
}
```

---

## 3. Neues Modul `js/quiz-abfrage.js`

Enthält die komplette Logik des neuen Quiz-Modus, eingebunden über einen neuen `<script>`-Tag in `index.html` nach `quiz.js`. Nutzt bestehende, unveränderte DOM-Struktur (`#quiz-wrapper`, `#image-pane`, `#zoom-container`, `#answer-panel`) sowie das bereits vorhandene responsive Layout (Bild+Panel nebeneinander im Querformat, übereinander im Hochformat) — keine CSS-Layout-Änderungen an diesem Grundgerüst nötig.

### 3.1 Ablauf beim Öffnen (`loadQuizAbfrage(entry, imgBasePath)`)

1. Bild wird geladen: `entry.filename` (das "clean"-Bild ohne Text-Labels, identisch zur Bildquelle im Schreiben-Modus).
2. Alle Nummern-Marker werden gerendert (wiederverwendet: `renderMarkers` aus `quiz.js`, siehe 3.4), zunächst ohne Hervorhebung.
3. `#answer-panel` zeigt den **Startbildschirm**: zwei Buttons "Der Reihe nach" und "Zufällig" zur Wahl der Abfrage-Reihenfolge.

### 3.2 Zustandsautomat

**Nach Wahl der Reihenfolge:**
- Sequenziell: `queue = [0, 1, ..., n-1]`
- Zufällig: `queue = shuffle([0, 1, ..., n-1])` (vollständig gemischt, inkl. erster Frage)
- Erste Frage: `currentIndex = queue.shift()`

**Zustand `asking`** (pro Frage):
- Panel zeigt: "Wie heißt die Struktur mit der Nummer `currentIndex + 1`?" + Button **"Antwort"**.
- Der Marker mit Nummer `currentIndex + 1` wird auf dem Bild hervorgehoben.

**Übergang zu Zustand `revealed`** (Klick auf "Antwort"):
- Korrekter Begriff (`entry.labels[currentIndex].text`) wird angezeigt.
- Darunter der Hinweistext "Meine Antwort war: korrekt oder falsch?" sowie die zwei Buttons **Korrekt** (grün) und **Falsch** (rot).
- Der "Antwort"-Button verschwindet.

**Klick auf Korrekt:**
- Aktuelle Frage wird verworfen (kein erneutes Einreihen).
- Sofort nächste Frage: `currentIndex = queue.shift()`.

**Klick auf Falsch:**
- `queue.push(currentIndex)` — Frage wandert ans Ende der Warteschlange.
- Sofort nächste Frage: `currentIndex = queue.shift()`.

**Warteschlange leer** (`queue.shift()` liefert `undefined`):
- **Abschluss-Bildschirm**: "Quiz abgeschlossen! Alle `n` Strukturen korrekt benannt." + Button "Neu starten".
- "Neu starten" führt zurück zum Startbildschirm (3.1, Schritt 3); Marker-Hervorhebung wird entfernt.

Es gibt keine Persistenz (kein LocalStorage) — passend zum Rest der App, die ebenfalls keinen Fortschritt speichert. Erneutes Öffnen von "Quiz" (gleiche oder andere Ansicht) verwirft jeden laufenden Zustand und startet `loadQuizAbfrage` komplett neu.

Kein Fortschritts-/Zähler-Anzeige (z. B. "noch X offen") — bewusst schlank gehalten.

### 3.3 Sonderfall: einzelnes Label

Entries mit nur einem Label funktionieren unverändert nach demselben Automaten (Quiz endet nach der ersten korrekten Antwort, ggf. nach mehreren Wiederholungen bei "Falsch").

### 3.4 Marker-Hervorhebung (Änderung an `js/quiz.js`)

`renderMarkers(labels, img, zoomContainer, highlightIndex)` bekommt einen optionalen 4. Parameter (Standard: keiner/`undefined`). Der Marker mit `i === highlightIndex` erhält zusätzlich die Klasse `marker-badge--active`. Bestehende Aufrufe aus dem Schreiben-Modus (ohne 4. Argument) bleiben unverändert.

### 3.5 Resize-Handling

Der bestehende globale `resize`-Listener in `quiz.js` ist aktuell direkt an `_currentEntry` gekoppelt (Flag für aktiven Schreiben-Modus) und ruft hart codiert `renderMarkers(_currentEntry.labels, img, zoomContainer)` auf (3 Argumente, keine Hervorhebung). Da `quiz.js` keine Modul-Kapselung nutzt (alle Top-Level-`var`s sind echte globale Variablen, genauso wie es `quiz-abfrage.js` als nachfolgendes `<script>`-Tag sein wird), wird `_currentEntry` durch einen generischen Callback-Hook ersetzt:

```js
var _activeMarkerRefresh = null; // Funktion ohne Argumente, oder null
```

- **Schreiben-Modus** (`loadQuiz`): setzt `_activeMarkerRefresh` auf eine Closure, die `renderMarkers(entry.labels, img, zoomContainer)` aufruft (kein Hervorhebungs-Index).
- **Quiz-Modus** (`loadQuizAbfrage`): setzt `_activeMarkerRefresh` auf eine Closure, die `renderMarkers(entry.labels, img, zoomContainer, currentIndex)` aufruft. `currentIndex` ist eine Variable im umschließenden Scope von `quiz-abfrage.js`, die bei jedem Frage-Wechsel neu zugewiesen wird — die Closure liest bei jedem Aufruf den aktuellen Wert (JS-Closures binden die Variable, nicht ihren Wert zum Zeitpunkt der Zuweisung).
- **Lernen-Modus** (`loadLernen`, `loadTextLernen`, `loadTextQuiz`): setzen `_activeMarkerRefresh = null` (wie bisher `_currentEntry = null`).

Der Resize-Listener vereinfacht sich zu:

```js
if (!_activeMarkerRefresh) return;
_activeMarkerRefresh();
```

Die Variable `_currentEntry` entfällt vollständig (ihre einzige bisherige Verwendung im Code ist dieser Resize-Gate; keine anderen Lese-/Schreibzugriffe im Projekt).

---

## 4. UI/Styling

- **Menü:** neue Klassen für den zweizeiligen Block (Label-Zeile + 3-Button-Zeile), angelehnt an bestehende Menü-Button-Stile (`.menu-ansicht-btn`, `.menu-lernen-btn`).
- **Quiz-Karte:** Frage-Text, "Antwort"-Button (Stil angelehnt an bestehende `.help-btn`/Modal-Buttons), Korrekt/Falsch-Buttons.
  - Grün (Korrekt) orientiert sich am bestehenden `#2a9d00` (siehe `#modal-close`, `.label-input.correct`).
  - Rot (Falsch) ist neu, z. B. `#c0392b`, konsistent zur bestehenden Signalfarben-Logik.
- **Start-/Abschluss-Bildschirm:** einfache Textblöcke mit Buttons, im `#answer-panel` gerendert, gleiche Typografie wie restliche App.
- **`.marker-badge--active`:** visuell abgesetzt vom Standard-`.number-badge` (z. B. größer und/oder farbiger Rahmen), um die aktuell gefragte Nummer auf dem Bild leicht auffindbar zu machen.

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `web/js/quiz-abfrage.js` | **Neu** — komplette Quiz-Abfrage-Logik |
| `web/js/quiz.js` | `renderMarkers` um optionalen `highlightIndex`-Parameter erweitert; `_currentEntry` durch generischen `_activeMarkerRefresh`-Callback-Hook ersetzt (Resize-Listener) |
| `web/js/menu.js` | Zweizeiliger Block (Label + Lernen/Schreiben/Quiz-Buttons) für Bild-Einträge |
| `web/js/app.js` | Routing um Modus `quiz` ergänzt |
| `web/index.html` | neuer `<script src="js/quiz-abfrage.js">` |
| `web/css/style.css` | neue Stile für Menü-Block, Quiz-Karte, Korrekt/Falsch-Buttons, `.marker-badge--active` |

---

## Nicht in diesem Scope

- Quiz-Modus für Text-Einträge (Excel/CSV-basiert)
- Fortschritts-/Zähler-Anzeige während des Quiz
- Persistenz des Quiz-Fortschritts (LocalStorage o. ä.)
- Freitext-Eingabefeld für die eigene Antwort ("Meine Antwort war" ist reiner Hinweistext, kein Eingabefeld)
