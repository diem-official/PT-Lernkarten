# Design: Dritte Reihenfolge-Option "Aus Liste" im Text-Quiz-Abfrage-Modus

**Datum:** 2026-08-24
**Status:** Freigegeben

---

## Ziel

Der bestehende Text-Quiz-Abfrage-Modus (`web/js/text-quiz-abfrage.js`, siehe `2026-08-24-text-quiz-abfrage-modus-design.md`) bietet auf dem Startbildschirm aktuell zwei Reihenfolge-Optionen: "Der Reihe nach" und "Zufällig". Beide fragen die (Zeile, Spalte)-Paare einzeln und linear ab.

Ergänzt wird eine dritte Option **"Aus Liste"**: Statt linearer Einzelabfrage zeigt das Panel eine vollständige, nach Zeile gruppierte Liste aller Fragen der aktuellen Ansicht (z. B. bei "Adduktoren": alle 6 Muskeln mit ihren Spalten Ursprung/Ansatz/Funktion/Innervation). Klick auf eine einzelne Spalte öffnet ein Pop-up mit der unveränderten Frage-/Antwort-/Bewertungs-Logik. Nach Bewertung schließt sich das Pop-up, und der entsprechende Listeneintrag erhält einen grünen Haken (korrekt) oder ein rotes Kreuz (falsch). Das Quiz endet automatisch (bestehender Abschlussbildschirm), sobald alle Einträge grün sind.

**Scope:** Nur der Text-Quiz-Abfrage-Modus (`text-quiz-abfrage.js`). Der Bild-Quiz-Modus (`quiz-abfrage.js`) ist nicht betroffen — keine Änderungen an dieser Datei.

---

## 1. Startbildschirm-Erweiterung

`showStartScreen()` erhält einen dritten Button **"Aus Liste"** neben den bestehenden `seqBtn`/`randomBtn`:

```js
var listBtn = _qzButton('qz-btn', 'Aus Liste');
listBtn.addEventListener('click', showListScreen);
panel.appendChild(listBtn);
```

---

## 2. Datenmodell für den Listen-Modus

Wiederverwendung der bestehenden Paar-Liste — keine neue Matching- oder Filter-Logik:

```js
pairs = _tqBuildQuizPairs(quizEntry);   // wie bisher, unverändert
```

Neu: ein Status-Array parallel zu `pairs`, nur im Listen-Modus verwendet. Wird als weitere `var` in den bestehenden Deklarationsblock am Anfang von `loadTextQuizAbfrage` aufgenommen (`var pairs = []; var queue = []; var currentIdx = null; var listStatus = [];`):

```js
listStatus = pairs.map(function () { return null; }); // null | 'correct' | 'wrong'
```

`pairs` ist bereits in Zeile×Spalte-Reihenfolge aufgebaut (siehe `_tqBuildQuizPairs`), daher lässt sich die Gruppierung nach Zeile durch einen einzigen sequenziellen Scan ableiten (keine Sortierung nötig):

```js
// Baut Gruppen { row, items: [{ pair, index }] } aus pairs, Zeilen-Reihenfolge
// bleibt erhalten (pairs ist bereits Zeile×Spalte-sortiert).
function _tqzGroupPairsByRow(pairs) {
    var groups = [];
    pairs.forEach(function (pair, index) {
        var last = groups[groups.length - 1];
        if (!last || last.row !== pair.row) {
            last = { row: pair.row, items: [] };
            groups.push(last);
        }
        last.items.push({ pair: pair, index: index });
    });
    return groups;
}
```

*(Hinweis: Da `pairs` garantiert nach Zeile gruppiert vorliegt, reicht ein simpler "gleiche Zeile wie letzte Gruppe?"-Vergleich; kein Objekt-Keying über Zeilennamen nötig, die theoretisch nicht eindeutig sein könnten.)*

---

## 3. Listen-Rendering (`showListScreen`)

```js
function showListScreen() {
    pairs = _tqBuildQuizPairs(quizEntry);
    listStatus = pairs.map(function () { return null; });
    renderList();
}

function renderList() {
    var panel = _tqzPanel();
    panel.classList.add('qz-panel--scrollable'); // siehe Abschnitt 7

    var heading = document.createElement('p');
    heading.className   = 'qz-heading';
    heading.textContent = 'Wähle eine Frage aus der Liste.';
    panel.appendChild(heading);

    _tqzGroupPairsByRow(pairs).forEach(function (group) {
        var groupEl = document.createElement('div');
        groupEl.className = 'qz-list-group';

        var rowLabel = document.createElement('p');
        rowLabel.className   = 'qz-category';
        rowLabel.textContent = group.row.question;
        groupEl.appendChild(rowLabel);

        var rowEl = document.createElement('div');
        rowEl.className = 'qz-list-row';

        group.items.forEach(function (item) {
            var btn = _qzButton('qz-btn', item.pair.colName);
            _tqzApplyStatus(btn, listStatus[item.index]);
            btn.addEventListener('click', function () {
                openQuestionModal(item.index);
            });
            rowEl.appendChild(btn);
        });

        groupEl.appendChild(rowEl);
        panel.appendChild(groupEl);
    });

    panelHost.appendChild(panel);
}

// Setzt/entfernt die Bewertungs-Darstellung eines Listen-Buttons. Nutzt die
// bereits bestehenden Klassen .qz-btn-correct/.qz-btn-wrong (identisch zu den
// Korrekt/Falsch-Buttons) — keine neue Farb-Regel nötig.
function _tqzApplyStatus(btn, status) {
    btn.classList.remove('qz-btn-correct', 'qz-btn-wrong');
    if (status === 'correct') {
        btn.classList.add('qz-btn-correct');
        btn.textContent = '✓ ' + btn.textContent.replace(/^[✓✗] /, '');
    } else if (status === 'wrong') {
        btn.classList.add('qz-btn-wrong');
        btn.textContent = '✗ ' + btn.textContent.replace(/^[✓✗] /, '');
    }
}
```

Bereits bewertete Einträge (grün oder rot) bleiben klickbar: erneuter Klick öffnet das Pop-up erneut, die neue Bewertung überschreibt die alte (`listStatus[index]` wird neu gesetzt, `renderList()` läuft danach erneut).

---

## 4. Gemeinsame Frage-/Antwort-Logik (Refactor)

Die Frage→Antwort→Bewertung-Logik existiert aktuell dupliziert as Closures in `showQuestion`/`showAnswer` (gebunden an `panelHost`). Sie wird in eine wiederverwendbare Funktion extrahiert, die einen beliebigen Container bespielt:

```js
// Rendert die Frage-Karte für `pair` in `container` (container wird geleert).
// Nach Bewertung (Korrekt/Falsch-Klick) wird onJudged('correct'|'wrong') aufgerufen
// — der Aufrufer entscheidet, was danach passiert (nächste Frage, Modal schließen, ...).
function _tqzRenderQuestionStep(container, pair, onJudged) {
    renderQuestion();

    function renderQuestion() {
        container.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';

        var label = document.createElement('p');
        label.className   = 'qz-category';
        label.textContent = pair.colName;
        panel.appendChild(label);

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = pair.row.question;
        panel.appendChild(question);

        var answerBtn = _qzButton('qz-btn qz-btn-primary', 'Antwort');
        answerBtn.addEventListener('click', renderAnswer);
        panel.appendChild(answerBtn);

        container.appendChild(panel);
    }

    function renderAnswer() {
        container.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';

        var label = document.createElement('p');
        label.className   = 'qz-category';
        label.textContent = pair.colName;
        panel.appendChild(label);

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = pair.row.question;
        panel.appendChild(question);

        var catEl = _buildCategoryBlock(pair.colName, pair.row.answers[pair.colName]);
        if (catEl) {
            var header = catEl.querySelector('.tq-category-header');
            if (header) header.remove();
            panel.appendChild(catEl);
        }

        var hint = document.createElement('p');
        hint.className   = 'qz-hint';
        hint.textContent = 'Meine Antwort war:';
        panel.appendChild(hint);

        var judgeRow = document.createElement('div');
        judgeRow.className = 'qz-judge-row';

        var correctBtn = _qzButton('qz-btn qz-btn-correct', 'Korrekt');
        correctBtn.addEventListener('click', function () { onJudged('correct'); });
        judgeRow.appendChild(correctBtn);

        var wrongBtn = _qzButton('qz-btn qz-btn-wrong', 'Falsch');
        wrongBtn.addEventListener('click', function () { onJudged('wrong'); });
        judgeRow.appendChild(wrongBtn);

        panel.appendChild(judgeRow);
        container.appendChild(panel);
    }
}
```

`showQuestion`/`showAnswer` in Sequenziell/Zufällig werden durch einen Aufruf dieser Funktion ersetzt:

```js
function askCurrent() {
    _tqzRenderQuestionStep(panelHost, pairs[currentIdx], function (verdict) {
        if (verdict === 'wrong') queue.push(currentIdx);
        nextQuestion();
    });
}
```

(`nextQuestion()` ruft statt `showQuestion()` künftig `askCurrent()` auf.)

Damit existiert die Frage-/Antwort-/Bewertungs-Darstellung nur noch an einer Stelle im Code und wird von beiden Modi (Panel-Inline und Modal) genutzt.

---

## 5. Pop-up (Modal)

Neues, einmalig lazy angelegtes Overlay-Element, **exakt** nach dem bestehenden Muster von `_openImageOverlay`/`#tq-image-overlay` in `quiz.js`: Idempotenz über `document.getElementById(...)` bei jedem Aufruf, **keine** JS-Variable als Cache.

**Wichtig — warum keine Cache-Variable:** `loadTextQuizAbfrage` läuft bei jedem Ansichtswechsel neu (erkennbar am bestehenden `_activeMarkerRefresh = null;` am Funktionsanfang). Eine `var _tqzModalOverlay = null;` *innerhalb* dieser Funktion würde daher bei jedem Wechsel zurückgesetzt, sodass `_tqzEnsureModal()` beim zweiten Öffnen von "Aus Liste" in derselben Session ein zweites, orphantes Overlay-Element erzeugen würde. Da `_tqzEnsureModal` deshalb **außerhalb** von `loadTextQuizAbfrage` auf Modul-Ebene stehen muss (analog zu `_openImageOverlay`, `_qzButton`, `_qzShuffle`), kann es ohnehin nicht auf `pairs`/`listStatus` zugreifen — das ist auch nicht nötig, denn diese Funktion baut nur das leere Overlay-Grundgerüst. Die Anbindung an die aktuellen Quiz-Daten passiert erst in `openQuestionModal` (siehe unten), die als Closure *innerhalb* von `loadTextQuizAbfrage` bleibt.

```js
// Modul-Ebene, außerhalb von loadTextQuizAbfrage (wie _qzButton, _qzShuffle).
// Idempotent über getElementById — keine Cache-Variable, da loadTextQuizAbfrage
// bei jedem Ansichtswechsel neu ausgeführt wird (siehe Begründung oben).
function _tqzEnsureModal() {
    var overlay = document.getElementById('tqz-question-modal');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'tqz-question-modal';
    overlay.className = 'qz-modal-overlay';

    var box = document.createElement('div');
    box.id = 'tqz-modal-box';
    box.className = 'qz-modal-box';
    overlay.appendChild(box);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.id = 'tqz-modal-close';
    closeBtn.className = 'tq-overlay-close';
    closeBtn.textContent = '×';
    closeBtn.setAttribute('aria-label', 'Schließen');
    closeBtn.addEventListener('click', function () {
        overlay.classList.remove('qz-modal-overlay--visible');
    });
    overlay.appendChild(closeBtn);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') overlay.classList.remove('qz-modal-overlay--visible');
    });

    document.body.appendChild(overlay);
    return overlay;
}
```

`openQuestionModal`/`closeQuestionModal` bleiben Closures *innerhalb* von `loadTextQuizAbfrage`, da sie `pairs`, `listStatus`, `renderList()` und `_tqzCheckFinished()` referenzieren:

```js
function openQuestionModal(pairIndex) {
    var overlay = _tqzEnsureModal();
    var box = document.getElementById('tqz-modal-box');

    _tqzRenderQuestionStep(box, pairs[pairIndex], function (verdict) {
        listStatus[pairIndex] = verdict;
        closeQuestionModal();
        renderList();
        _tqzCheckFinished(); // überschreibt die gerade gerenderte Liste sofort
                              // mit dem Abschlussbildschirm, falls alles korrekt
                              // ist — synchron, kein sichtbares Flackern
    });

    overlay.classList.add('qz-modal-overlay--visible');
    document.getElementById('tqz-modal-close').focus();
}

function closeQuestionModal() {
    document.getElementById('tqz-question-modal').classList.remove('qz-modal-overlay--visible');
}
```

Schließen über den `×`-Button oder Escape bewertet **nicht** — `listStatus` bleibt unverändert, kein `renderList()`/`_tqzCheckFinished()`-Aufruf nötig (analog zum bestehenden Bild-Overlay: Abbrechen ändert keinen Zustand).

---

## 6. Abschluss-Erkennung

```js
function _tqzCheckFinished() {
    var allCorrect = listStatus.length > 0 && listStatus.every(function (s) {
        return s === 'correct';
    });
    if (allCorrect) showFinishScreen(); // bestehende Funktion, unverändert
}
```

`showFinishScreen()` bleibt unverändert (Text "Quiz abgeschlossen! Alle N Fragen korrekt beantwortet." + "Neu starten" → zurück zu `showStartScreen()`).

---

## 7. CSS-Ergänzungen (`web/css/style.css`)

Minimal, da Buttons/Panel/Bewertungsfarben vollständig aus dem bestehenden `.qz-*`-Satz wiederverwendet werden (`.qz-panel`, `.qz-btn`, `.qz-btn-primary`, `.qz-btn-correct`, `.qz-btn-wrong`, `.qz-judge-row`, `.qz-category`, `.qz-heading`, `.qz-hint`). Neu:

```css
/* Overlay-Grundgerüst, analog zu .tq-image-overlay */
.qz-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}
.qz-modal-overlay--visible {
    display: flex;
}
.qz-modal-box {
    background: #fff;
    border-radius: 10px;
    padding: 28px 32px;
    max-width: 400px;
    width: 90vw;
    box-shadow: 0 6px 30px rgba(0, 0, 0, 0.3);
}

/* Listen-Modus: Gruppierung nach Zeile */
.qz-list-group {
    margin-bottom: 18px;
}
.qz-list-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 6px;
}

/* Ohne Bild (.tq-quiz-standalone) hat .qz-panel keine Höhenbegrenzung; bei
   vielen Zeilen (z. B. 8 Muskeln × 4 Spalten) muss die Liste scrollen statt
   über den Viewport hinauszuragen. Nur für den Listen-Modus gesetzt. */
.qz-panel--scrollable {
    max-height: 90vh;
    overflow-y: auto;
}
```

Wiederverwendet ohne Änderung: `.tq-overlay-close` (Schließen-Button-Stil, bereits für `.tq-image-overlay` definiert).

---

## 8. Betroffene Dateien

| Datei | Änderung |
|---|---|
| `web/js/text-quiz-abfrage.js` | Dritter Startbildschirm-Button "Aus Liste"; `listStatus` ergänzt den bestehenden Deklarationsblock (`pairs`/`queue`/`currentIdx`) in `loadTextQuizAbfrage`; neue Closures `showListScreen`, `renderList`, `_tqzApplyStatus`, `openQuestionModal`, `closeQuestionModal`, `_tqzCheckFinished`, `askCurrent` (ersetzt `showQuestion` als Aufrufer von `nextQuestion()`) innerhalb von `loadTextQuizAbfrage`; neue Modul-Ebene-Funktionen `_tqzGroupPairsByRow`, `_tqzEnsureModal` (analog zu `_qzButton`/`_qzShuffle`, außerhalb von `loadTextQuizAbfrage`); Refactor von `showQuestion`/`showAnswer` zu gemeinsamem `_tqzRenderQuestionStep` — ebenfalls Modul-Ebene, da sie nur ihre Parameter (`container`/`pair`/`onJudged`) und bestehende Globals (`_buildCategoryBlock`, `_qzButton`) nutzt, keine Closure-Variablen aus `loadTextQuizAbfrage` — genutzt von `askCurrent` und `openQuestionModal` |
| `web/css/style.css` | Neu: `.qz-modal-overlay`, `.qz-modal-overlay--visible`, `.qz-modal-box`, `.qz-list-group`, `.qz-list-row`, `.qz-panel--scrollable` |

---

## Nicht in diesem Scope

- Änderungen am Bild-Quiz-Modus (`quiz-abfrage.js`) — keine "Aus Liste"-Option dort.
- Persistenz des Listen-Fortschritts (LocalStorage o. Ä.) — Zustand lebt nur in der laufenden Session, wie der Rest der App.
- Fortschritts-/Zähler-Anzeige zusätzlich zu den Haken/Kreuzen in der Liste selbst.
- Sortier-/Filter-Optionen innerhalb der Liste (z. B. "nur offene Fragen anzeigen").
