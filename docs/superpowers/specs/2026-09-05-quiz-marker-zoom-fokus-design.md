# Design: Marker-Gegenskalierung und Auto-Fokus im Quiz-Abfrage-Modus

**Datum:** 2026-09-05
**Status:** Freigegeben

---

## Ziel

Im Quiz-Abfrage-Modus (`quiz-abfrage.js`) überlappen sich die Zahlen-Marker auf dem Bild häufig, wenn viele Strukturen eng beieinander liegen. Das ist bei voller Bildansicht (Zoom-Faktor 1) akzeptabel, wird aber zum Problem, sobald der Nutzer in eine überlappende Stelle hineinzoomt: aktuell wachsen die Marker mit dem Bild mit, sodass die Überlappung erhalten bleibt statt sich aufzulösen.

Zwei Verhaltensänderungen:

1. **Marker-Gegenskalierung:** Beim Hineinzoomen behalten die Zahlen-Marker ihre Bildschirmgröße (px) bei, statt mit dem Bild mitzuwachsen. Da der Abstand zwischen den Strukturen beim Zoomen größer wird, die Marker aber gleich groß bleiben, lösen sich Überlappungen auf.
2. **Auto-Fokus auf aktuellen Marker:** Wechselt die Frage im Abfrage-Modus (`nextQuestion()`), während das Bild gezoomt ist, wird die Ansicht so verschoben, dass der neu abgefragte Marker sichtbar im Ausschnitt liegt — aber nur minimal, wenn er tatsächlich außerhalb oder zu nah am Rand liegt (kein "Kamera-Springen" wenn er schon sichtbar ist). Sofortiger Sprung, keine Animation.

**Scope:** Nur der sequenzielle Abfrage-Modus (`quiz-abfrage.js`, wo es einen eindeutigen `currentIndex` gibt). Der Schreiben-Modus (`loadQuiz`, alle Marker gleichzeitig ohne Hervorhebung) und das Text-Quiz-Bild-Overlay (keine Marker vorhanden) bleiben bewusst unverändert.

---

## 1. `web/js/zoom.js`: `onTransform`-Hook und `focusPoint()`

### 1.1 `createZoom(el, opts)`: optionaler `opts.onTransform`-Callback

`createZoom` bekommt einen neuen zweiten, optionalen Parameter `opts`. Direkt zu Beginn: `opts = opts || {};` (bestehender Aufruf ohne zweites Argument — `_overlayZoom = window.createZoom(zoomCont);` im Text-Quiz-Overlay, `quiz.js:221` — muss unverändert weiterlaufen).

Am Ende von `applyTransform()` wird — nach dem Setzen von `container.style.transform` — `if (opts.onTransform) opts.onTransform(state);` aufgerufen. Der Callback feuert bei jeder Transform-Änderung (Wheel-Zoom, Pinch, Drag-Pan, `zoomAt`, `resetZoom`, künftig auch `focusPoint`), da alle diese Pfade durch `applyTransform()` laufen.

`initZoom(el, opts)` (der Backwards-Compat-Wrapper, `zoom.js:219-222`, aufgerufen an der einzigen Callsite `quiz.js:614`) reicht `opts` unverändert an `createZoom(el, opts)` durch.

### 1.2 `focusPoint(x, y)`

Neue Methode auf dem von `createZoom()` zurückgegebenen Objekt (zusätzlich zu `reset`). `x`/`y` sind Container-lokale Koordinaten — dieselbe Koordinatenraum, die auch für Marker-`left`/`top` verwendet wird (Bild-Pixel bei Zoom-Faktor 1, siehe `renderMarkers`).

Ablauf (spiegelt exakt die in `zoomAt()`/`getNaturalOffset()` bereits verwendete Koordinatentransformation, `zoom.js:32-38` und `60-70` — `#zoom-container` ist flexbox-zentriert in seinem Elternrahmen, `state.tx`/`ty` sind *zusätzliche* Verschiebung obendrauf):

1. Ist `state.s <= 1` (nicht gezoomt), sofort zurückkehren (no-op) — bei voller Bildansicht ist ohnehin alles sichtbar.
2. `var off = getNaturalOffset();` (bestehende Funktion, liefert den Zentrierungs-Offset).
3. Bildschirmposition des Punkts berechnen: `screenX = off.x + state.tx + x * state.s`, `screenY = off.y + state.ty + y * state.s` — **wichtig:** der `off.x/off.y`-Term darf nicht weggelassen werden, sonst ist die Rand-Berechnung bei nicht quadratischem Letterboxing (z. B. Hochformat-Bilder in einem breiteren Panel) systematisch falsch.
4. Sichtbare Fläche bestimmen über `container.parentElement.getBoundingClientRect()` (dieselbe Quelle wie in `getNaturalOffset()`, `onWheel()`, `getTouchMid()` — **nicht** `el.clientWidth`/`clientHeight`, das wäre der Zoom-Container selbst, nicht dessen Elternrahmen).
5. Eine Rand-Marge definieren (z. B. 30px) und prüfen, ob `screenX`/`screenY` außerhalb von `[marge, rect.width - marge]` bzw. `[marge, rect.height - marge]` liegt.
6. Falls außerhalb: `state.tx`/`state.ty` um genau die Differenz verschieben, die nötig ist, um den Punkt an die nächstliegende Marge zu bringen (keine Zentrierung, keine Überkorrektur) — Semantik wie `scrollIntoView`. Liegt der Punkt bereits innerhalb der Marge, passiert nichts (kein Aufruf von `applyTransform()`, keine sichtbare Änderung).
7. `clampState()` (bestehend) anwenden, um leere Ränder zu verhindern, dann `applyTransform()`.
8. Kein CSS-`transition` — sofortiger Sprung, wie bei den übrigen Zoom-Operationen.

### 1.3 `getScale()`

Zusätzliche, triviale neue Methode auf dem zurückgegebenen Objekt: `getScale: function () { return state.s; }`. Wird gebraucht, weil `renderMarkers()` (siehe 2.2) beim Neu-Erzeugen der Badges den aktuell tatsächlich geltenden Zoom-Faktor kennen muss — etwa wenn ein Resize während des Zoomens `renderMarkers()` erneut aufruft (siehe Abschnitt 4, Edge Case "Resize") und dabei alle Badges neu erzeugt (bestehendes Verhalten: `renderMarkers()` entfernt und erzeugt alle `.marker-badge`-Elemente neu, `quiz.js:71`). Ohne `getScale()` hätte `renderMarkers()` keine Möglichkeit, die Gegenskalierung korrekt mit dem aktuellen `s` statt einem geratenen Default (z. B. `1`) zu initialisieren.

Der von `createZoom()` zurückgegebene Objekt-Umfang wird damit zu: `{ reset: resetZoom, focusPoint: focusPoint, getScale: getScale }`.

Keine Race Condition beim ersten `renderMarkers()`-Aufruf: `initZoom()` läuft synchron in `quiz.js`s eigenem `DOMContentLoaded`-Handler (`quiz.js:613-614`). `loadQuiz`/`loadLernen`/`loadQuizAbfrage` werden dagegen ausschließlich aus dem Menü-Klick-Callback in `app.js` aufgerufen, der selbst erst nach einem asynchronen `fetch()` innerhalb von `app.js`s eigenem `DOMContentLoaded`-Handler feuert — also immer erst, nachdem alle synchronen `DOMContentLoaded`-Listener (inkl. `initZoom`) bereits gelaufen sind. `window.getZoomScale`/`window.focusZoomPoint` sind damit zum Zeitpunkt jedes ersten `renderMarkers()`-Aufrufs garantiert gesetzt.

---

## 2. `web/js/quiz.js`: Marker-Gegenskalierung

Wichtige Randbedingung (im ursprünglichen Entwurf übersehen): Es existiert nur **eine einzige** Zoom-Instanz für `#zoom-container`, einmalig erzeugt beim Laden der Seite (`quiz.js:613-614`, `DOMContentLoaded` → `initZoom(...)`). Lernen-, Schreiben- und Abfrage-Modus teilen sich dieselbe Instanz und denselben Container — `loadQuiz`/`loadLernen`/`loadQuizAbfrage` erzeugen selbst keine neue Zoom-Instanz. Der `onTransform`-Hook (1.1) feuert deshalb unabhängig vom aktuell aktiven Modus. Da die Gegenskalierung laut Scope **nur** im Abfrage-Modus gelten soll (Schreiben-Modus bleibt unverändert), braucht es ein explizites Moduswächter-Flag statt die Skalierung bedingungslos auf alle `.marker-badge`-Elemente anzuwenden.

### 2.1 Neues Flag `_markerCounterScaleEnabled`

Neue modul-globale Variable neben `_activeMarkerRefresh` (`quiz.js:5`):

```js
var _markerCounterScaleEnabled = false;
```

- **Quiz-Modus** (`loadQuizAbfrage`, `quiz-abfrage.js`): setzt `_markerCounterScaleEnabled = true` beim Öffnen.
- **Schreiben-Modus** (`loadQuiz`) und **Lernen-Modus** (`loadLernen`): setzen `_markerCounterScaleEnabled = false`.

### 2.2 Skalierungs-Logik

Neuer Helfer in `quiz.js`:

```js
function applyMarkerCounterScale(zoomContainer, s) {
    zoomContainer.querySelectorAll('.marker-badge').forEach(function (badge) {
        badge.style.transform = 'translate(-50%, -50%) scale(' + (1 / s) + ')';
    });
}
```

Verwendet von zwei Stellen, beide gegen `_markerCounterScaleEnabled` gewächtert:
- **`renderMarkers()`** (`quiz.js:67-82`): direkt nach dem Erzeugen der Badges, mit dem tatsächlich aktuellen Zoom-Faktor über die neue `getScale()`-Methode (1.3): `if (_markerCounterScaleEnabled) applyMarkerCounterScale(zoomContainer, window.getZoomScale());` — relevant z. B. wenn ein Resize während des Zoomens die Badges neu erzeugt (siehe Abschnitt 4).
- **Dem `onTransform`-Hook** (siehe 2.3): `if (_markerCounterScaleEnabled) applyMarkerCounterScale(zoomContainer, state.s);` — bei jeder Zoom-/Pan-Änderung wird nur die Skalierung nachgezogen, kein kompletter Re-Render (Position bleibt unverändert, nur `transform`).

### 2.3 Verdrahtung der Zoom-Instanz

`initZoom` wird um `opts` erweitert und reicht sie durch (siehe 1.1). Die einzige Callsite (`quiz.js:613-614`) wird zu:

```js
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'), {
        onTransform: function (state) {
            if (_markerCounterScaleEnabled) {
                applyMarkerCounterScale(document.getElementById('zoom-container'), state.s);
            }
        }
    });
});
```

Für `focusPoint()` (Aufruf aus `quiz-abfrage.js`, siehe Abschnitt 3) muss zusätzlich die Zoom-Instanz selbst erreichbar sein — aktuell exponiert `initZoom` nur `.reset` als `window.resetZoom` (`zoom.js:219-222`). Analog dazu wird ergänzt:

```js
window.initZoom = function (el, opts) {
    var instance = window.createZoom(el, opts);
    window.resetZoom    = instance.reset;
    window.focusZoomPoint = instance.focusPoint;
    window.getZoomScale = instance.getScale;
};
```

`quiz-abfrage.js` ruft dann direkt die globale Funktion `focusZoomPoint(cx, cy)` auf (kein zusätzliches Moduswächter-Flag nötig, da nur der Abfrage-Modus diese Funktion überhaupt aufruft — `focusPoint()` selbst ist zoom-state-getrieben und macht bei `s <= 1` ohnehin nichts, siehe 1.2). `renderMarkers()` in `quiz.js` ruft analog `window.getZoomScale()` auf (siehe 2.2).

---

## 3. `web/js/quiz-abfrage.js`: Auto-Fokus bei Fragenwechsel

`nextQuestion()` (`quiz-abfrage.js:67-74`) setzt aktuell nur `currentIndex = queue.shift();` und ruft danach `showQuestion()` auf; der Marker-Refresh (`_activeMarkerRefresh()`) passiert erst **innerhalb** von `showQuestion()` (Zeile 77), nicht in `nextQuestion()` selbst. Der neue Fokus-Aufruf wird direkt in `nextQuestion()` eingefügt, unmittelbar nach der Zuweisung von `currentIndex` und vor dem Aufruf von `showQuestion()`:

```js
function nextQuestion() {
    if (queue.length === 0) {
        showFinishScreen();
        return;
    }
    currentIndex = queue.shift();

    if (window.focusZoomPoint) {
        var label = entry.labels[currentIndex];
        var scaleX = img.clientWidth  / img.naturalWidth;
        var scaleY = img.clientHeight / img.naturalHeight;
        var cx = (label.mask_box.x + label.mask_box.w / 2) * scaleX;
        var cy = (label.mask_box.y + label.mask_box.h / 2) * scaleY;
        window.focusZoomPoint(cx, cy);
    }

    showQuestion();
}
```

`scaleX`/`scaleY` werden hier bewusst **dupliziert** statt aus `renderMarkers()` (`quiz.js:68-69`) wiederverwendet: es sind nur zwei triviale Einzeiler, `quiz-abfrage.js` hält bereits eine eigene `img`-Referenz (Zeile 7), und ein gemeinsamer Helfer (z. B. `getImageScale(img)`) wäre für zwei Aufrufstellen unnötige Abstraktion (YAGNI).

---

## 4. Edge Cases

- **Resize:** Der bestehende debounced Resize-Handler in `quiz.js` (`quiz.js:597-610`) ruft `_activeMarkerRefresh()` auf, was `renderMarkers()` erneut aufruft und dabei alle Badges neu erzeugt. Dank `getScale()` (1.3) liest `renderMarkers()` dabei den tatsächlich aktuellen Zoom-Faktor statt eines Default-Werts — die Gegenskalierung bleibt so auch nach einem Resize-während-gezoomt korrekt erhalten. (Separat davon läuft `zoom.js`s eigener, kürzer debouncter Resize-Handler, `zoom.js:205-213`, der nur `clampState()`/`applyTransform()` aufruft und damit ohnehin schon den `onTransform`-Hook feuert.)
- **Quiz-Start:** `resetZoom()` läuft beim Öffnen eines Eintrags im Abfrage-Modus (`loadQuizAbfrage`, vor dem Startbildschirm, `quiz-abfrage.js:24`), `s` = 1 → `focusPoint()` bei der ersten Frage ist ein No-op, sofern der Nutzer im Startbildschirm (Auswahl "Der Reihe nach"/"Zufällig") noch nicht selbst gezoomt hat. Zoomt er dort bereits hinein, greift `focusPoint()` schon bei Frage 1 — das ist konsistent mit dem beabsichtigten Verhalten, kein Sonderfall nötig.
- **Sehr hoher Zoom / kleiner sichtbarer Bereich:** Das bestehende `clampState()` verhindert leere Ränder; `focusPoint()` kann den Marker im Extremfall nur so nah wie möglich an den sichtbaren Rand bringen, statt ihn vollständig freizustellen — akzeptiertes Verhalten, kein Sonderfall nötig.
- **Text-Quiz-Bild-Overlay** (`_openImageOverlay`): hat keine Marker → unberührt von beiden Änderungen.
- **Schreiben-Modus** (`loadQuiz`): bewusst unverändert — Marker wachsen dort weiterhin mit dem Zoom mit, kein Fokus-Verhalten, da es keinen eindeutigen "aktuellen" Marker gibt.

---

## 5. Testing

Manuelle Verifikation via Playwright (siehe [[testing_this_app_with_playwright]] — `chromium-cli` ist hier nicht installiert, direkt Playwright nutzen):

- Abfrage-Quiz öffnen, per Wheel-Event/Programmatic-Call reinzoomen (Faktor 1.0 → 4.0), prüfen dass `getBoundingClientRect()`-Breite/-Höhe der `.marker-badge`-Elemente über alle Zoom-Stufen konstant bleibt (~22px Standard, ~28px `--active`).
- Bei hohem Zoom in eine Bildecke wegpannen (fernab vom nächsten abgefragten Marker), dann `nextQuestion()` auslösen (z. B. "Falsch" klicken) → prüfen, dass der neue Marker danach innerhalb des sichtbaren Ausschnitts liegt.
- Regressionscheck: Resize-Verhalten weiterhin korrekt (Position + Gegenskalierung nach Resize erhalten).
- Regressionscheck: Schreiben-Modus und Text-Quiz-Bild-Overlay unverändert (keine Gegenskalierung, kein Fokus-Sprung).

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `web/js/zoom.js` | `createZoom(el, opts)` und `initZoom(el, opts)` bekommen optionalen zweiten Parameter; neuer `opts.onTransform`-Callback in `applyTransform()`; neue Methoden `focusPoint(x, y)` und `getScale()`; `initZoom` exponiert zusätzlich `window.focusZoomPoint` und `window.getZoomScale` (analog zu `window.resetZoom`) |
| `web/js/quiz.js` | Neue modul-globale Variable `_markerCounterScaleEnabled` (Deklaration, Default `false`); gesetzt auf `false` in `loadQuiz`/`loadLernen`; `renderMarkers()` wendet bei aktivem Flag Gegenskalierung an (`applyMarkerCounterScale()`, neuer Helfer, nutzt `window.getZoomScale()`); `onTransform`-Callback an der `initZoom`-Callsite (`quiz.js:613-614`) wendet Gegenskalierung bei jeder Zoom-/Pan-Änderung erneut an |
| `web/js/quiz-abfrage.js` | `loadQuizAbfrage()` setzt `_markerCounterScaleEnabled = true` beim Öffnen (Variable ist modul-global in `quiz.js` deklariert, analog zu `_activeMarkerRefresh` aus quiz-abfrage.js heraus beschreibbar); `nextQuestion()` ruft nach dem Setzen von `currentIndex` `window.focusZoomPoint(cx, cy)` auf, vor `showQuestion()` |

---

## Nicht in diesem Scope

- Marker-Gegenskalierung oder Fokus-Verhalten im Schreiben-Modus (`loadQuiz`)
- Marker im Text-Quiz-Bild-Overlay (existieren dort nicht)
- Animierte Übergänge beim Auto-Fokus (bewusst sofortiger Sprung)
- Automatisches Verändern des Zoom-Faktors beim Fragenwechsel (nur Pan, kein Re-Zoom)
