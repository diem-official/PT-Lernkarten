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

### 1.1 `onTransform`-Callback

`createZoom(el, opts)` akzeptiert ein neues optionales `opts.onTransform`. Am Ende von `applyTransform()` wird — nach dem Setzen von `container.style.transform` — `opts.onTransform({tx, ty, s})` aufgerufen, falls vorhanden. Der Callback feuert bei jeder Transform-Änderung (Wheel-Zoom, Pinch, Drag-Pan, `zoomAt`, `resetZoom`), da alle diese Pfade durch `applyTransform()` laufen.

### 1.2 `focusPoint(x, y)`

Neue Methode auf dem von `createZoom()` zurückgegebenen Objekt. `x`/`y` sind Container-lokale Koordinaten — dieselbe Koordinatenraum, die auch für Marker-`left`/`top` verwendet wird (Bild-Pixel bei Zoom-Faktor 1, siehe `renderMarkers`).

Ablauf:
1. Ist `state.s <= 1` (nicht gezoomt), sofort zurückkehren (no-op) — bei voller Bildansicht ist ohnehin alles sichtbar.
2. Bildschirmposition des Punkts berechnen: `screenX = state.tx + x * state.s`, `screenY = state.ty + y * state.s` (relativ zum `#zoom-container`, dessen positionierter Elternrahmen die sichtbare Fläche (`el.clientWidth`/`clientHeight`) vorgibt).
3. Eine Rand-Marge definieren (z. B. 30px) und prüfen, ob `screenX`/`screenY` außerhalb von `[marge, breite - marge]` bzw. `[marge, höhe - marge]` liegt.
4. Falls außerhalb: `state.tx`/`state.ty` um genau die Differenz verschieben, die nötig ist, um den Punkt an die nächstliegende Marge zu bringen (keine Zentrierung, keine Überkorrektur) — Semantik wie `scrollIntoView`.
5. `clampState()` (bestehend) anwenden, um leere Ränder zu verhindern, dann `applyTransform()`.
6. Kein CSS-`transition` — sofortiger Sprung, wie bei den übrigen Zoom-Operationen.

Liegt der Punkt bereits innerhalb der Marge, passiert nichts (kein Aufruf von `applyTransform()`, keine sichtbare Änderung).

---

## 2. `web/js/quiz.js`: Marker-Gegenskalierung

### 2.1 Skalierungs-Logik

`renderMarkers(labels, img, zoomContainer, highlightIndex)` liest den aktuellen Zoom-Faktor `s` der zugehörigen Zoom-Instanz (Referenz analog zu `_activeMarkerRefresh` verfügbar, siehe 2.2) und setzt zusätzlich zu `left`/`top`:

```js
badge.style.transform = 'translate(-50%, -50%) scale(' + (1 / s) + ')';
```

Ein kleiner Helfer `applyMarkerCounterScale(zoomContainer, s)` iteriert über alle vorhandenen `.marker-badge`-Elemente in `zoomContainer` und setzt nur den `transform` neu (ohne `left`/`top` anzufassen). Er wird verwendet von:
- `renderMarkers()` selbst (direkt nach dem Erzeugen der Badges, mit dem zum Render-Zeitpunkt aktuellen `s`),
- dem `onTransform`-Hook der Quiz-Zoom-Instanz (siehe 2.2) — bei jeder Zoom-/Pan-Änderung wird nur die Skalierung nachgezogen, kein kompletter Re-Render (Position bleibt unverändert, nur `transform`).

### 2.2 Verdrahtung der Zoom-Instanz

Die Zoom-Instanz für das Haupt-Quiz-Bild (aktuell über `initZoom` als Backwards-Compat-Wrapper erzeugt, `quiz.js:614`) wird mit `onTransform: function (state) { applyMarkerCounterScale(zoomContainer, state.s); }` erzeugt. Die Instanz selbst wird zusätzlich in einer modul-globalen Referenz `_activeZoomApi` gehalten (gleiches Muster wie `_activeMarkerRefresh`), damit `quiz-abfrage.js` `focusPoint()` aufrufen kann, ohne dass `quiz.js`/`quiz-abfrage.js` sich gegenseitig direkt importieren (beide sind ohnehin nur nacheinander geladene `<script>`-Tags mit globalen `var`s, siehe bestehendes Muster in [[testing_this_app_with_playwright|Codebase]]).

- **Quiz-Modus** (`loadQuizAbfrage`): setzt `_activeZoomApi` auf die erzeugte Zoom-Instanz.
- **Schreiben-/Lernen-Modus:** setzt `_activeZoomApi = null` (kein Fokus-Verhalten dort nötig/gewünscht).

---

## 3. `web/js/quiz-abfrage.js`: Auto-Fokus bei Fragenwechsel

`nextQuestion()` ruft nach dem Setzen von `currentIndex` und `_activeMarkerRefresh()` (bestehend, rendert Hervorhebung neu) zusätzlich:

```js
if (_activeZoomApi && currentIndex != null) {
    var label = entry.labels[currentIndex];
    var cx = (label.mask_box.x + label.mask_box.w / 2) * scaleX;
    var cy = (label.mask_box.y + label.mask_box.h / 2) * scaleY;
    _activeZoomApi.focusPoint(cx, cy);
}
```

`scaleX`/`scaleY` sind dieselben Werte, die auch `renderMarkers()` zur Positionierung verwendet (`img.clientWidth / img.naturalWidth` bzw. Höhe-Äquivalent) — müssen ggf. an einer zugänglichen Stelle berechnet/wiederverwendet werden, statt sie zu duplizieren.

---

## 4. Edge Cases

- **Resize:** Der bestehende debounced Resize-Handler ruft `_activeMarkerRefresh()` auf, was `renderMarkers()` erneut mit dem aktuellen `s` aufruft — die Gegenskalierung wird dabei automatisch mit neu gesetzt, kein zusätzlicher Code nötig.
- **Quiz-Start:** `resetZoom()` läuft bereits beim Start eines Quiz-Durchlaufs (`s` = 1) → `focusPoint()` bei der ersten Frage ist automatisch ein No-op (siehe 1.2, Schritt 1).
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
| `web/js/zoom.js` | Neuer `opts.onTransform`-Callback in `createZoom()`; neue Methode `focusPoint(x, y)` |
| `web/js/quiz.js` | `renderMarkers()` setzt Gegenskalierung (`transform: scale(1/s)`) auf alle Badges; neuer Helfer `applyMarkerCounterScale()`; neue modul-globale Referenz `_activeZoomApi`, gesetzt in `loadQuizAbfrage`/`loadQuiz`/`loadLernen` |
| `web/js/quiz-abfrage.js` | `nextQuestion()` ruft nach Fragenwechsel `_activeZoomApi.focusPoint(cx, cy)` auf |

---

## Nicht in diesem Scope

- Marker-Gegenskalierung oder Fokus-Verhalten im Schreiben-Modus (`loadQuiz`)
- Marker im Text-Quiz-Bild-Overlay (existieren dort nicht)
- Animierte Übergänge beim Auto-Fokus (bewusst sofortiger Sprung)
- Automatisches Verändern des Zoom-Faktors beim Fragenwechsel (nur Pan, kein Re-Zoom)
