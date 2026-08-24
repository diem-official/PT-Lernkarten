# Design: Neuer Quiz-Abfrage-Modus für Text-Ansichten

**Datum:** 2026-08-24
**Status:** Freigegeben

---

## Ziel

Ergänzung eines dritten Modus **Quiz** für Text-Einträge (`text-data.json`, `entry.type === 'text'`), analog zum bereits umgesetzten Quiz-Abfrage-Modus für Bild-Ansichten (siehe `2026-08-24-quiz-abfrage-modus-design.md`). Statt der bisherigen zwei Modi (Lernen, Schreiben) bekommen Text-Ansichten damit ebenfalls eine Einzelabfrage mit Selbsteinschätzung (Korrekt/Falsch) statt Texteingabe-Validierung.

**Kernunterschied zum Bild-Quiz-Modus:** Die Antworten in `text-data.json` sind bewusst kurz gehalten (Effizienz beim Schreiben-Modus). Für den Quiz-Modus sollen stattdessen ausführlichere, wissensreichere Antworten angezeigt werden. Diese werden **nicht** in `text-data.json` ergänzt, sondern in einer neuen, eigenständigen Datei gepflegt, die künftig durch ein separates (hier nicht behandeltes) Befüll-Skript erweitert wird.

**Scope:** Nur Text-Einträge. Der bestehende Bild-Quiz-Modus (`quiz-abfrage.js`) ist nicht betroffen.

---

## 1. Neue Datei `web/data/text-quiz-data.json`

Eigenständige Spiegel-Datei: identische Top-Level-Struktur wie `text-data.json` (`type`, `subject`, `category`, `subcategory`, `view`, optional `image`/`images`, `columns`, `rows` mit `question` + `answers`), aber mit inhaltlich erweiterten Antworten.

**Inhaltsstil:** Gleiche Array-Struktur pro Spalte (mehrere Fragmente), jedes Fragment wird zu einem vollständigen, erklärenden Satz ausgeschrieben statt eines kurzen Stichworts. Das bestehende `"Präfix: Lösung"`-Muster (z. B. Winkelangaben wie `"<70°: ..."`) bleibt erhalten und wird weiterhin über `_parseAnswer` (Split am ersten Doppelpunkt) geparst — bei der Content-Erstellung ist daher auf einen sauberen ersten Doppelpunkt als Trenner zu achten, falls ein Präfix verwendet wird.

Beispiel (Ausschnitt, `M. obturatorius externus`, Spalte "Funktion"):

```json
// text-data.json (kurz)
"Funktion": ["Adduktion", "Außenrotation", "Stabil Sagittalebene"]

// text-quiz-data.json (erweitert)
"Funktion": [
  "Adduktion des Hüftgelenks, wirkt bei gestrecktem Bein am stärksten",
  "Außenrotation im Hüftgelenk",
  "Stabilisiert das Becken in der Sagittalebene, besonders beim einbeinigen Stand"
]
```

**Matching (statt struktureller Kopplung):** Die App lädt `text-quiz-data.json` separat und **nicht** als Teil von `allData`/Menüaufbau. Beim Öffnen von "Quiz" für einen Text-Eintrag wird der passende Eintrag über die vier Identitätsfelder gesucht:

```
subject === entry.subject && category === entry.category
  && subcategory === entry.subcategory && view === entry.view
```

Innerhalb des gefundenen Eintrags wird die passende Zeile über `row.question` (exakte Gleichheit, z. B. Muskelname) gematcht — kein Index-basiertes Matching, robuster gegen spätere Umsortierung in einer der beiden Dateien.

**Begründung:** Beide Dateien bleiben unabhängig pflegbar; das künftige Befüll-Skript kann pro `text-data.json`-Eintrag unabhängig eine angereicherte Zwillings-Version erzeugen, ohne Kenntnis der jeweils anderen Datei. Kleine Kehrseite: `columns`/`question` werden dupliziert (Drift möglich) — abgefedert durch den Fallback in Abschnitt 4 (kein Fehler, nur ein Hinweistext bei fehlendem Match).

---

## 2. Menü-Struktur (`js/menu.js`)

Text-Ansichten erhalten denselben zweizeiligen Block wie Bild-Ansichten (siehe `2026-08-24-quiz-abfrage-modus-design.md`, Abschnitt 1), für ein einheitliches Erscheinungsbild:

- **Zeile 1:** nicht-klickbares Label mit dem Ansicht-Namen.
- **Zeile 2:** drei Buttons **Lernen / Schreiben / Quiz**.

Der bisherige "Ansicht-Name ✒"-Button (Doppelfunktion: Label + Schreiben-Auslöser) entfällt zugunsten dieser Struktur. "Schreiben" löst weiterhin denselben Modus wie bisher aus (`onSelect(entry, 'schreiben')`). "Quiz" ist neu: `onSelect(entry, 'quiz')`.

---

## 3. Routing & Datenladen (`js/app.js`)

Dritter `fetch` (parallel zu `DATA_URL`/`TEXT_DATA_URL` via `Promise.all`) lädt `text-quiz-data.json` in eine Variable `textQuizData` (Array, wie die anderen beiden). Bei Fehlern/leerer Datei: `[]` (analog zum bestehenden Fallback für `TEXT_DATA_URL`).

Der `onSelect`-Callback erweitert seine Verzweigung für Text-Einträge:

```js
if (entry.type === 'text') {
    if (mode === 'lernen')      loadTextLernen(entry, OG_IMG_BASE);
    else if (mode === 'quiz')   loadTextQuizAbfrage(entry, IMG_BASE, textQuizData);
    else                        loadTextQuiz(entry, IMG_BASE); // 'schreiben'
} else {
    // unverändert: Bild-Routing
}
```

---

## 4. Neues Modul `js/text-quiz-abfrage.js`

Neuer `<script>`-Tag in `index.html` nach `quiz-abfrage.js`. Nutzt bestehende Helper aus `quiz.js` (`_parseAnswer`, `_textWrapperSetup`, `_normalizeImages`, `_buildImageEl`) sowie die generischen `_qz*`-Helper und CSS-Klassen aus dem Bild-Quiz-Modus (`_qzButton`, `_qzShuffle`, `.qz-panel`, `.qz-question`, `.qz-btn-correct`, `.qz-btn-wrong` etc.) — eigenes CSS für Buttons/Panel entfällt dadurch fast komplett.

### 4.1 Ablauf beim Öffnen (`loadTextQuizAbfrage(entry, imgBase, textQuizData)`)

1. Passenden Eintrag in `textQuizData` suchen (Matching siehe Abschnitt 1).
2. **Kein Match:** `#answer-panel` zeigt nur den Hinweistext "Noch keine Quiz-Daten für diese Ansicht vorhanden." — kein Startbildschirm, keine Warteschlange.
3. **Match gefunden:** Referenzbild der Ansicht wird angezeigt (falls `entry.image`/`entry.images` vorhanden, gleiche Bildquelle wie im Schreiben-Modus via `_normalizeImages`/`_buildImageEl`). Das Bild bleibt während der gesamten Quiz-Session unverändert sichtbar — Text-Antworten haben keine nummerierten Bildmarker wie der Bild-Quiz-Modus, daher keine Hervorhebung nötig.
4. `#answer-panel` zeigt den Startbildschirm: Buttons "Der Reihe nach" / "Zufällig" (Reihenfolge-Wahl, wie im Bild-Quiz-Modus).

### 4.2 Zustandsautomat

**Warteschlangen-Aufbau** (nach Wahl der Reihenfolge): Liste aller `(row, colName)`-Paare aus allen Zeilen des gematchten Eintrags, in Reihenfolge `rows` × `columns`. Spalten mit leerem Namen (`""`) oder leerem/gefiltertem Antwort-Array werden übersprungen (gleiche Filterung wie bestehend: `(row.answers[colName] || []).filter(a => a)`).

- Sequenziell: Paare in natürlicher Reihenfolge.
- Zufällig: vollständig gemischt (`_qzShuffle`, inkl. erstes Paar).

**Zustand `asking`** (pro Frage):
- Panel zeigt zwei getrennte Elemente (bewusst **kein** zusammengesetzter Satz):
  - Spalten-Label (`colName`), Stil wie `.tq-category-label`.
  - `row.question` als eigenständiger Fragetext darunter, Stil wie `.qz-question`.
- Button **"Antwort"**.

  *Begründung für die Trennung:* Bei anatomischen Zeilen ist `row.question` ein Strukturname (z. B. `"M. obturatorius externus"`), bei anderen Einträgen (z. B. Hydrotherapie) bereits ein vollständiger Satz (z. B. `"Nenne jeweils 5 Indikationen und Kontraindikationen..."`). Eine grammatische Verkettung mit dem Spaltennamen (`"{colName} von {question}"`) würde im zweiten Fall unsinnige Sätze erzeugen. Getrennte Anzeige funktioniert in beiden Fällen.

**Übergang zu Zustand `revealed`** (Klick auf "Antwort"):
- Die erweiterten Antwort-Fragmente der aktuellen Spalte werden als Liste gerendert — gleiche Darstellung wie im Lernen-Modus (Kategorie-Block: Fragmente einzeln, inkl. Präfix-Handling über `_parseAnswer`), aus dem gemeinsamen Helper (siehe 4.4).
- Darunter Hinweistext "Meine Antwort war:" + Buttons **Korrekt** (grün) / **Falsch** (rot) — wiederverwendet aus dem Bild-Quiz-Modus (`.qz-btn-correct`, `.qz-btn-wrong`).
- "Antwort"-Button verschwindet.

**Klick auf Korrekt:** aktuelles Paar verworfen, sofort nächste Frage.
**Klick auf Falsch:** Paar ans Ende der Warteschlange, sofort nächste Frage.

**Warteschlange leer:** Abschlussbildschirm "Quiz abgeschlossen! Alle N Fragen korrekt beantwortet." (N = Gesamtzahl der `(row, colName)`-Paare) + Button "Neu starten" (zurück zum Startbildschirm, 4.1 Schritt 4).

Keine Persistenz (kein LocalStorage), kein Fortschritts-/Zähler-Anzeige während der Abfrage — konsistent zum Bild-Quiz-Modus und zum Rest der App.

### 4.3 Sonderfall: nur eine Zeile mit wenigen Spalten

Entries mit nur einer Zeile (z. B. Hydrotherapie) funktionieren unverändert nach demselben Automaten — die Warteschlange enthält dann nur so viele Paare wie befüllte Spalten in dieser einen Zeile.

### 4.4 Code-Reuse: gemeinsamer Kategorie-Block-Helper

Die Rendering-Logik für einen Kategorie-Block (Label-Header + Liste der geparsten Antwort-Fragmente inkl. Präfix-Span) existiert aktuell nur in `loadTextLernen` (`js/quiz.js`). Sie wird in eine kleine Helper-Funktion extrahiert (z. B. `_buildAnswerListBlock(colName, answers)`, gibt ein DOM-Element zurück) und von `loadTextLernen` **und** vom Antwort-Reveal in `text-quiz-abfrage.js` genutzt. Vermeidet eine dritte Kopie derselben Logik neben `loadTextLernen` und `loadTextQuiz`.

---

## 5. UI/Styling

Keine neuen CSS-Klassen für Buttons/Panel/Zustände nötig — vollständige Wiederverwendung der `.qz-*`-Klassen aus dem Bild-Quiz-Modus (`.qz-panel`, `.qz-heading`, `.qz-question`, `.qz-btn`, `.qz-btn-primary`, `.qz-btn-correct`, `.qz-btn-wrong`, `.qz-judge-row`) sowie `.tq-category-label`/`.tq-answer-text`/`.tq-field-prefix` aus dem bestehenden Text-Rendering.

Einzige Ergänzung: Menü-Struktur für Text-Einträge nutzt die bereits bestehenden Klassen `.menu-ansicht-label`/`.menu-ansicht-actions`/`.menu-mode-btn` aus dem Bild-Quiz-Menü (keine neuen Klassen).

---

## 6. Initiale Inhalte (dieser Durchgang, kein Skript)

Für den Start wird `text-quiz-data.json` einmalig manuell mit den 5 bestehenden Views (21 Zeilen aus `text-data.json`) befüllt — Antworten erweitert nach dem in Abschnitt 1 festgelegten Stil. Dies ist reine Inhaltserstellung auf Basis der bestehenden `text-data.json`, **kein** wiederverwendbares Skript — das künftige automatisierte Befüll-Skript ist ausdrücklich **nicht** Teil dieses Vorhabens. Die fertige Datei wird vor Einbindung fachlich geprüft.

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `web/data/text-quiz-data.json` | **Neu** — Spiegel-Datei mit erweiterten Antworten, initial für 5 bestehende Views befüllt |
| `web/js/text-quiz-abfrage.js` | **Neu** — komplette Text-Quiz-Abfrage-Logik |
| `web/js/quiz.js` | Kategorie-Block-Rendering aus `loadTextLernen` in gemeinsamen Helper extrahiert |
| `web/js/menu.js` | Text-Einträge auf zweizeiligen Block (Label + Lernen/Schreiben/Quiz-Buttons) umgestellt |
| `web/js/app.js` | Dritter Fetch für `text-quiz-data.json`; Routing um Modus `quiz` für Text-Einträge ergänzt |
| `web/index.html` | neuer `<script src="js/text-quiz-abfrage.js">` |

---

## Nicht in diesem Scope

- Das künftige automatisierte Befüll-Skript für `text-quiz-data.json`
- Fortschritts-/Zähler-Anzeige während des Quiz
- Persistenz des Quiz-Fortschritts (LocalStorage o. ä.)
- Freitext-Eingabefeld für die eigene Antwort (reiner Hinweistext, kein Eingabefeld)
- Änderungen am bestehenden Bild-Quiz-Modus (`quiz-abfrage.js`)
