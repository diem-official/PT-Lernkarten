# Marker-Gegenskalierung und Auto-Fokus im Quiz-Abfrage-Modus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Quiz-Abfrage-Modus sollen die Zahlen-Marker beim Hineinzoomen ihre Bildschirmgröße behalten (statt mit dem Bild mitzuwachsen), damit sich Überlappungen auflösen, und die Ansicht soll bei jedem Fragenwechsel minimal nachpannen, damit der aktuell abgefragte Marker sichtbar bleibt.

**Architecture:** `zoom.js` (generische Pan/Zoom-Engine, CSS `transform: translate() scale()` auf `#zoom-container`) bekommt einen `onTransform`-Callback-Hook sowie zwei neue Methoden `focusPoint(x, y)` (minimal pannen, damit ein Punkt sichtbar ist) und `getScale()`. `quiz.js` nutzt den Hook, um alle `.marker-badge`-Elemente bei jeder Zoom-/Pan-Änderung gegen zu skalieren (`scale(1/s)`), gesteuert über ein neues Moduswächter-Flag `_markerCounterScaleEnabled` (nur im Abfrage-Modus aktiv, da Lernen/Schreiben-Modus dieselbe Zoom-Instanz und denselben Container teilen). `quiz-abfrage.js` ruft bei jedem Fragenwechsel die neue `focusPoint()`-Funktionalität auf.

**Tech Stack:** Vanilla JS (kein Build-Step, `<script>`-Tags), CSS. Verifikation manuell/per Playwright (kein automatisierter Test-Runner in diesem Repo).

**Spec:** `docs/superpowers/specs/2026-09-05-quiz-marker-zoom-fokus-design.md` (dreifach reviewt, freigegeben)

---

## Hinweise für die Umsetzung

- Es gibt **keine** automatisierten Tests in diesem Repo (kein `package.json`, kein Test-Runner). Verifikation erfolgt manuell per Playwright-Skript gegen den lokal servierten `web/`-Ordner (`python3 -m http.server 8099` aus `web/`). Details: siehe Memory `testing_this_app_with_playwright` — `chromium-cli` ist **nicht** installiert, Playwright direkt nutzen; npm-Paketversion und gecachte Browser-Revision müssen zusammenpassen; bei Menü-Selektoren `:visible` anhängen (mehrere Einträge mit gleichem Label existieren versteckt im DOM).
- Alle Playwright-Verifikationsskripte sind Wegwerf-Skripte — im eigenen Scratchpad-Verzeichnis ablegen, **nicht** ins Repo committen.
- Nach jedem Task: `git add` nur die tatsächlich geänderten Dateien (nicht die Verifikationsskripte im Scratchpad) und committen.
- **Wichtig zu Codeausschnitten in diesem Plan:** `zoom.js` ist komplett in ein IIFE (`(function () { ... }());`) gewrappt — der echte Code ist dadurch um eine Einrückungsebene tiefer als in den folgenden Snippets gezeigt. Die Snippets in diesem Plan sind inhaltlich exakt, aber **nicht** auf Whitespace-Ebene verlässlich — beim tatsächlichen Editieren (z. B. mit einem Edit-Tool, das exakte String-Übereinstimmung braucht) immer zuerst die echte Datei lesen und den `old_string` mit der dort tatsächlich vorhandenen Einrückung bilden, nicht blind aus diesem Plan kopieren.

---

### Task 1: `web/js/zoom.js` — `onTransform`-Hook, `focusPoint()`, `getScale()`

**Files:**
- Modify: `web/js/zoom.js:8` (Funktionssignatur `createZoom`), `web/js/zoom.js:19-22` (`applyTransform`), `web/js/zoom.js:215-216` (Return-Objekt), `web/js/zoom.js:219-222` (`initZoom`)

Aktueller Stand dieser Stellen (zur Orientierung, Einrichtung hier vereinfacht — siehe Hinweis oben):

```js
// Zeile 8
window.createZoom = function (el) {
    var container = el;
    var state = { s: 1, tx: 0, ty: 0 };
    ...

// Zeile 19-22
function applyTransform() {
    container.style.transform =
        'translate(' + state.tx + 'px, ' + state.ty + 'px) scale(' + state.s + ')';
}

// Zeile 215-216
        return { reset: resetZoom };
    };

    // Backwards-compatible wrapper for the image quiz.
    window.initZoom = function (el) {
        var instance = window.createZoom(el);
        window.resetZoom = instance.reset;
    };
```

- [ ] **Step 1: `createZoom` akzeptiert `opts` und ruft `onTransform` in `applyTransform()` auf**

In `web/js/zoom.js`, Zeile 8, Funktionssignatur ändern:

```js
window.createZoom = function (el, opts) {
    opts = opts || {};
    var container = el;
    var state = { s: 1, tx: 0, ty: 0 };
```

`applyTransform()` (Zeile 19-22) erweitern:

```js
function applyTransform() {
    container.style.transform =
        'translate(' + state.tx + 'px, ' + state.ty + 'px) scale(' + state.s + ')';
    if (opts.onTransform) opts.onTransform(state);
}
```

- [ ] **Step 2: Manuell prüfen, dass der bestehende Ein-Argument-Aufruf nicht bricht**

`web/js/quiz.js:221` ruft `window.createZoom(zoomCont)` ohne zweites Argument auf (Text-Quiz-Bild-Overlay). Kurz per Node nachvollziehen, dass `opts || {}` bei `undefined` zu `{}` wird (keine echte Testausführung nötig, reine Syntax-/Logik-Prüfung):

Run: `node -e "var opts; opts = opts || {}; console.log(JSON.stringify(opts));"`
Expected: `{}`

- [ ] **Step 3: `focusPoint(x, y)` implementieren**

Direkt vor `resetZoom()` (aktuell Zeile 72) einfügen — nutzt dieselbe Koordinatentransformation wie `zoomAt()` (Zeile 60-70) und `getNaturalOffset()` (Zeile 32-38):

```js
function focusPoint(x, y) {
    if (state.s <= 1) return;

    var off = getNaturalOffset();
    var screenX = off.x + state.tx + x * state.s;
    var screenY = off.y + state.ty + y * state.s;

    var rect = container.parentElement.getBoundingClientRect();
    var margin = 30;

    var dx = 0, dy = 0;
    if (screenX < margin) dx = margin - screenX;
    else if (screenX > rect.width - margin) dx = (rect.width - margin) - screenX;
    if (screenY < margin) dy = margin - screenY;
    else if (screenY > rect.height - margin) dy = (rect.height - margin) - screenY;

    if (dx === 0 && dy === 0) return;

    state.tx += dx;
    state.ty += dy;
    clampState();
    applyTransform();
}
```

- [ ] **Step 4: `getScale()` implementieren**

Direkt danach einfügen:

```js
function getScale() {
    return state.s;
}
```

- [ ] **Step 5: Neue Methoden im Return-Objekt exponieren**

Zeile 215 (`return { reset: resetZoom };`) ändern zu:

```js
        return { reset: resetZoom, focusPoint: focusPoint, getScale: getScale };
    };
```

- [ ] **Step 6: `initZoom` erweitern — `opts` durchreichen, neue globale Hooks exponieren**

Zeile 219-222 ändern zu:

```js
    // Backwards-compatible wrapper for the image quiz.
    window.initZoom = function (el, opts) {
        var instance = window.createZoom(el, opts);
        window.resetZoom      = instance.reset;
        window.focusZoomPoint = instance.focusPoint;
        window.getZoomScale   = instance.getScale;
    };
```

- [ ] **Step 7: Playwright-Smoke-Check — neue globale Funktionen sind nach Seitenaufruf vorhanden und liefern plausible Werte**

Im Scratchpad-Verzeichnis (nicht im Repo) ein Skript `verify-zoom-api.js` anlegen:

```js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto('http://localhost:8099/index.html');

    const scaleBeforeAnyLoad = await page.evaluate(() => window.getZoomScale());
    console.log('getZoomScale() vor jedem Bild-Laden:', scaleBeforeAnyLoad);
    if (scaleBeforeAnyLoad !== 1) throw new Error('Erwartet: 1, bekommen: ' + scaleBeforeAnyLoad);

    const hasFocusPoint = await page.evaluate(() => typeof window.focusZoomPoint === 'function');
    console.log('focusZoomPoint ist Funktion:', hasFocusPoint);
    if (!hasFocusPoint) throw new Error('window.focusZoomPoint fehlt');

    // s <= 1 -> focusPoint() ist No-op, darf nicht werfen
    await page.evaluate(() => window.focusZoomPoint(100, 100));

    console.log('OK');
    await browser.close();
})();
```

Voraussetzung: lokaler Server läuft (`cd "web" && python3 -m http.server 8099`), Playwright-Paket installiert (siehe Memory `testing_this_app_with_playwright` falls `npm install playwright` noch nicht im Scratchpad passiert ist).

Run: `node verify-zoom-api.js` (im Scratchpad-Verzeichnis)
Expected: Ausgabe endet mit `OK`, kein Fehler/Exception.

- [ ] **Step 8: Commit**

```bash
git add "web/js/zoom.js"
git commit -m "$(cat <<'EOF'
feat: zoom.js um onTransform-Hook, focusPoint() und getScale() erweitern

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `web/js/quiz.js` — Marker-Gegenskalierung (Flag, Helper, Verdrahtung)

**Files:**
- Modify: `web/js/quiz.js:5` (neue Variable), `web/js/quiz.js:9-29` (`loadLernen`), `web/js/quiz.js:33-62` (`loadQuiz`), `web/js/quiz.js:67-82` (`renderMarkers`), `web/js/quiz.js:613-615` (`initZoom`-Aufruf)

- [ ] **Step 1: Neues Flag deklarieren**

Zeile 5 (`var _activeMarkerRefresh = null; // ...`) — direkt danach eine neue Zeile einfügen:

```js
var _activeMarkerRefresh = null; // Funktion ohne Argumente, oder null (für den Resize-Listener)
var _markerCounterScaleEnabled = false; // true nur im Abfrage-Quiz-Modus (quiz-abfrage.js)
```

- [ ] **Step 2: Flag in `loadLernen` explizit auf `false` setzen**

`web/js/quiz.js:10` (`_activeMarkerRefresh = null;` innerhalb von `loadLernen`) — Zeile direkt danach ergänzen:

```js
function loadLernen(entry, ogImgBasePath) {
    _activeMarkerRefresh = null;
    _markerCounterScaleEnabled = false;
```

- [ ] **Step 3: Flag in `loadQuiz` explizit auf `false` setzen**

`web/js/quiz.js:34` (`_imgBasePath  = imgBasePath;` innerhalb von `loadQuiz`) — Zeile direkt danach ergänzen:

```js
function loadQuiz(entry, imgBasePath) {
    _imgBasePath  = imgBasePath;
    _markerCounterScaleEnabled = false;
```

- [ ] **Step 4: `applyMarkerCounterScale()`-Helper hinzufügen und in `renderMarkers()` verwenden**

`renderMarkers()` (Zeile 67-82) am Ende erweitern und direkt danach den neuen Helper einfügen:

```js
function renderMarkers(labels, img, zoomContainer, highlightIndex) {
    var scaleX = img.clientWidth  / img.naturalWidth;
    var scaleY = img.clientHeight / img.naturalHeight;

    zoomContainer.querySelectorAll('.marker-badge').forEach(function (el) { el.remove(); });

    labels.forEach(function (label, i) {
        var badge = document.createElement('div');
        badge.className   = 'marker-badge number-badge';
        if (i === highlightIndex) badge.classList.add('marker-badge--active');
        badge.textContent = i + 1;
        badge.style.left  = ((label.mask_box.x + label.mask_box.w / 2) * scaleX) + 'px';
        badge.style.top   = ((label.mask_box.y + label.mask_box.h / 2) * scaleY) + 'px';
        zoomContainer.appendChild(badge);
    });

    if (_markerCounterScaleEnabled) {
        applyMarkerCounterScale(zoomContainer, window.getZoomScale());
    }
}

// Hält die Bildschirmgröße der Marker beim Zoomen konstant (statt mit dem
// Bild mitzuwachsen), damit sich eng beieinanderliegende Marker beim
// Hineinzoomen entzerren statt überlappt zu bleiben.
function applyMarkerCounterScale(zoomContainer, s) {
    zoomContainer.querySelectorAll('.marker-badge').forEach(function (badge) {
        badge.style.transform = 'translate(-50%, -50%) scale(' + (1 / s) + ')';
    });
}
```

- [ ] **Step 5: `onTransform`-Hook an der `initZoom`-Callsite verdrahten**

Zeile 613-615:

```js
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'));
```

ändern zu:

```js
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'), {
        onTransform: function (state) {
            if (_markerCounterScaleEnabled) {
                applyMarkerCounterScale(document.getElementById('zoom-container'), state.s);
            }
        }
    });
```

(Die schließende Klammer/Semikolon der bestehenden Zeile danach unverändert lassen.)

- [ ] **Step 6: Playwright-Check — Schreiben-Modus bleibt unverändert (Regression)**

Skript `verify-schreiben-regression.js` im Scratchpad:

```js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto('http://localhost:8099/index.html');

    // Menü: irgendeinen Bild-Eintrag im Schreiben-Modus öffnen.
    // Anpassen an tatsächliche Menüstruktur — Platzhalter-Selektoren, ggf.
    // im Browser-Inspector die echten Label-Texte prüfen. ':visible' nutzen,
    // da Label-Texte im Menü mehrfach (versteckt) vorkommen.
    await page.locator('text=Anatomie:visible').first().click(); // Beispiel — anpassen
    // ... Navigation bis zu einem Bild-Eintrag, dann "Schreiben" klicken ...

    // WICHTIG: zoom.js hängt den wheel-Listener direkt auf #zoom-container
    // (nicht auf document/window), Wheel-Events bubbeln nur vom tatsächlichen
    // Ziel-Element aus nach oben. Die virtuelle Maus muss deshalb zuerst
    // ÜBER das Bild bewegt werden, sonst landet das Wheel-Event außerhalb
    // des Containers und wird nie verarbeitet (state.s ändert sich nie,
    // der Test würde sonst mit falsch-negativem/-positivem Ergebnis "OK"
    // melden statt die Ursache zu erkennen).
    const pane = await page.locator('#image-pane').boundingBox();
    await page.mouse.move(pane.x + pane.width / 2, pane.y + pane.height / 2);

    // WICHTIG: onWheel() in zoom.js nutzt nur das VORZEICHEN von deltaY
    // (fester ZOOM_STEP von 0.12 pro Event), nicht dessen Betrag. Ein
    // einzelner wheel-Call landet also immer nur bei s=1.12, egal wie groß
    // deltaY ist — deshalb hier mehrfach in kleinen Schritten aufrufen, um
    // tatsächlich deutlich hineinzuzoomen (Richtung ZOOM_MAX=4.0).
    for (let i = 0; i < 15; i++) {
        await page.mouse.wheel(0, -100); // negatives deltaY = rein, laut onWheel()
    }

    const size = await page.locator('.marker-badge').first().boundingBox();
    console.log('Marker-Größe im Schreiben-Modus nach Zoom:', size.width, size.height);
    if (size.width <= 30) throw new Error('Marker sollte im Schreiben-Modus WEITER mitwachsen, ist aber klein geblieben');

    console.log('OK — Schreiben-Modus unverändert (Marker wächst mit Zoom mit)');
    await browser.close();
})();
```

Run: `node verify-schreiben-regression.js`
Expected: `OK — Schreiben-Modus unverändert ...` (Marker-Breite deutlich über den üblichen 22px, da mit dem Zoom mitgewachsen).

Hinweis: Die Menü-Selektoren im Skript sind Platzhalter — beim Ausführen zunächst `page.locator('.menu-ansicht-btn, .menu-lernen-btn, button:visible').allTextContents()` loggen, um die tatsächlichen Labels/Klassen zu finden, dann Selektoren anpassen.

- [ ] **Step 7: Commit**

```bash
git add "web/js/quiz.js"
git commit -m "$(cat <<'EOF'
feat: Marker-Gegenskalierung beim Zoomen (nur wenn _markerCounterScaleEnabled)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `web/js/quiz-abfrage.js` — Flag aktivieren + Auto-Fokus bei Fragenwechsel

**Files:**
- Modify: `web/js/quiz-abfrage.js:24-28` (`loadQuizAbfrage`, nach `resetZoom()`), `web/js/quiz-abfrage.js:67-74` (`nextQuestion`)

- [ ] **Step 1: `_markerCounterScaleEnabled = true` beim Öffnen des Abfrage-Modus setzen**

Aktueller Stand (Zeile 21-28):

```js
    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    _activeMarkerRefresh = function () {
        renderMarkers(entry.labels, img, zoomContainer, currentIndex);
    };
```

Ändern zu:

```js
    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();
    _markerCounterScaleEnabled = true;

    _activeMarkerRefresh = function () {
        renderMarkers(entry.labels, img, zoomContainer, currentIndex);
    };
```

- [ ] **Step 2: `focusZoomPoint()` in `nextQuestion()` aufrufen**

Aktueller Stand (Zeile 67-74):

```js
    function nextQuestion() {
        if (queue.length === 0) {
            showFinishScreen();
            return;
        }
        currentIndex = queue.shift();
        showQuestion();
    }
```

Ändern zu:

```js
    function nextQuestion() {
        if (queue.length === 0) {
            showFinishScreen();
            return;
        }
        currentIndex = queue.shift();

        if (window.focusZoomPoint) {
            var label  = entry.labels[currentIndex];
            var scaleX = img.clientWidth  / img.naturalWidth;
            var scaleY = img.clientHeight / img.naturalHeight;
            window.focusZoomPoint(
                (label.mask_box.x + label.mask_box.w / 2) * scaleX,
                (label.mask_box.y + label.mask_box.h / 2) * scaleY
            );
        }

        showQuestion();
    }
```

(Der `if (window.focusZoomPoint)`-Guard ist laut Spec bewusst eine Absicherung gegen künftige Lade-Reihenfolge-Änderungen — auch wenn Task 1 in diesem Plan immer zuerst läuft und die Funktion zur Laufzeit stets existiert.)

- [ ] **Step 3: Playwright-Check — Marker-Gegenskalierung im Abfrage-Modus**

Skript `verify-marker-counterscale.js` im Scratchpad (Selektoren analog Task 2 Step 6 anpassen, aber "Quiz"-Button statt "Schreiben" klicken):

```js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto('http://localhost:8099/index.html');

    // ... Navigation bis zu einem Bild-Eintrag, dann "Quiz" klicken,
    //     dann "Der Reihe nach" im Startbildschirm ...

    const sizeBefore = await page.locator('.marker-badge').first().boundingBox();
    console.log('Marker-Größe vor Zoom:', sizeBefore.width);

    // Maus zuerst über das Bild bewegen (wheel-Listener sitzt auf
    // #zoom-container, Events bubbeln nur vom echten Ziel aus), dann in
    // kleinen Schritten mehrfach zoomen (onWheel() nutzt nur das Vorzeichen
    // von deltaY, fester ZOOM_STEP=0.12 pro Event — siehe Task 2 Step 6).
    const pane = await page.locator('#image-pane').boundingBox();
    await page.mouse.move(pane.x + pane.width / 2, pane.y + pane.height / 2);
    for (let i = 0; i < 15; i++) {
        await page.mouse.wheel(0, -100);
    }

    const sizeAfter = await page.locator('.marker-badge').first().boundingBox();
    console.log('Marker-Größe nach Zoom:', sizeAfter.width);

    if (Math.abs(sizeAfter.width - sizeBefore.width) > 3) {
        throw new Error('Marker-Größe hat sich verändert — Gegenskalierung greift nicht');
    }

    console.log('OK — Marker-Größe bleibt beim Zoomen konstant');
    await browser.close();
})();
```

Run: `node verify-marker-counterscale.js`
Expected: `OK — Marker-Größe bleibt beim Zoomen konstant`

- [ ] **Step 4: Playwright-Check — Auto-Fokus bringt weggepannten Marker zurück ins Bild**

Skript `verify-focus-on-question-change.js` im Scratchpad:

```js
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto('http://localhost:8099/index.html');

    // ... Navigation bis zu einem Bild-Eintrag, "Quiz", "Der Reihe nach" ...

    // Maus zuerst über das Bild bewegen (wheel-Listener sitzt auf
    // #zoom-container, Events bubbeln nur vom echten Ziel aus), dann in
    // kleinen Schritten mehrfach zoomen (onWheel() nutzt nur das Vorzeichen
    // von deltaY, fester ZOOM_STEP=0.12 pro Event). Reicht hier bewusst
    // weiter als in den anderen Skripten (mehr Zoom = mehr Spielraum zum
    // Wegpannen).
    const pane = await page.locator('#image-pane').boundingBox();
    await page.mouse.move(pane.x + pane.width / 2, pane.y + pane.height / 2);
    for (let i = 0; i < 20; i++) {
        await page.mouse.wheel(0, -100);
    }

    // In eine Ecke wegpannen (weit weg vom nächsten Marker) — Drag-Geste.
    // onMouseDown() in zoom.js ist selbst ein No-op solange state.s <= 1,
    // daher ist der vorherige Zoom-Schritt Voraussetzung dafür, dass diese
    // Pan-Geste überhaupt etwas bewirkt.
    await page.mouse.down();
    await page.mouse.move(pane.x + pane.width - 5, pane.y + pane.height - 5, { steps: 10 });
    await page.mouse.up();

    // "Antwort" -> "Falsch" klicken, um nextQuestion() auszulösen
    await page.locator('button:has-text("Antwort")').click();
    await page.locator('button:has-text("Falsch")').click();

    const activeMarker = await page.locator('.marker-badge--active').boundingBox();
    const paneBox = await page.locator('#image-pane').boundingBox();

    const visible = activeMarker.x >= paneBox.x && activeMarker.x <= paneBox.x + paneBox.width &&
                    activeMarker.y >= paneBox.y && activeMarker.y <= paneBox.y + paneBox.height;

    console.log('Aktiver Marker nach Fragenwechsel im sichtbaren Bereich:', visible);
    if (!visible) throw new Error('Aktiver Marker liegt außerhalb des sichtbaren Ausschnitts');

    console.log('OK — Auto-Fokus bringt Marker zurück ins Bild');
    await browser.close();
})();
```

Run: `node verify-focus-on-question-change.js`
Expected: `OK — Auto-Fokus bringt Marker zurück ins Bild`

- [ ] **Step 5: Commit**

```bash
git add "web/js/quiz-abfrage.js"
git commit -m "$(cat <<'EOF'
feat: Auto-Fokus auf aktuellen Marker im Quiz-Abfrage-Modus aktivieren

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Vollständige manuelle Regressionsprüfung

**Files:** keine Code-Änderungen — reine Verifikation.

- [ ] **Step 1: Resize-während-gezoomt (Abfrage-Modus)**

Manuell im Browser (oder per Playwright `page.setViewportSize`): Abfrage-Quiz öffnen, reinzoomen, Browserfenster-Breite ändern (triggert `quiz.js`-Resize-Handler, 120ms debounced, siehe `quiz.js:597-610`), prüfen dass Marker-Größe weiterhin konstant bleibt (nicht auf Vollgröße zurückspringt).

Erwartet: Marker-Bounding-Box-Breite bleibt ~22px (bzw. ~28px für den aktiven Marker) nach dem Resize.

- [ ] **Step 2: Text-Quiz-Bild-Overlay unverändert**

Text-Quiz mit Bild-Unterstützung öffnen, Bild antippen/vergrößern (Overlay-Zoom, `_openImageOverlay` in `quiz.js`). Da dort keine `.marker-badge`-Elemente existieren, gibt es nichts zu prüfen außer: Overlay öffnet weiterhin fehlerfrei (kein `TypeError` durch den neuen `opts.onTransform`-Zugriff, siehe Task 1 Step 2).

Erwartet: Keine Fehler in der Browser-Konsole beim Öffnen/Zoomen des Overlays.

- [ ] **Step 3: Lernen-Modus unverändert**

Lernen-Modus für einen Bild-Eintrag öffnen (keine Marker, nur Originalbild). Reinzoomen, prüfen dass keine Fehler auftreten.

Erwartet: Keine Fehler in der Browser-Konsole.

- [ ] **Step 4: Quiz-Start ohne vorheriges Zoomen — kein ungewollter Sprung bei Frage 1**

Abfrage-Quiz öffnen, direkt "Der Reihe nach" wählen (ohne im Startbildschirm zu zoomen) — Ansicht darf bei Frage 1 nicht springen (da `s` = 1, `focusPoint()` ist No-op, siehe Spec Abschnitt 4).

Erwartet: Keine sichtbare Zoom-/Pan-Änderung beim Start von Frage 1.

- [ ] **Step 5: Alle Verifikationsskripte aus Task 1-3 gebündelt noch einmal laufen lassen**

Run: alle vier `.js`-Skripte aus den vorherigen Tasks nacheinander im Scratchpad ausführen.
Expected: Alle enden mit `OK ...`, keine Exceptions.

- [ ] **Step 6: Scratchpad-Verifikationsskripte NICHT committen**

```bash
git status
```

Erwartet: Nur die drei bereits committeten Dateien (`zoom.js`, `quiz.js`, `quiz-abfrage.js`) tauchen in der Historie auf, keine offenen Änderungen im Arbeitsverzeichnis (Verifikationsskripte liegen außerhalb des Repos im Scratchpad).

---

## Nicht in diesem Plan

- Marker-Gegenskalierung oder Fokus-Verhalten im Schreiben-Modus
- Animierte Übergänge (bewusst sofortiger Sprung, siehe Spec)
- Änderung des Zoom-Faktors selbst beim Fragenwechsel (nur Pan)
