# Mobile Responsive Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mache die Lernkarten-App auf Smartphones (≤ 600px Hochkantformat) vollständig nutzbar — mit Hamburger-Menü, Slide-in Drawer und Pinch/Scroll-Zoom auf dem Anatomie-Bild.

**Architecture:** Mobile-Layout via CSS Media Query (`@media (max-width: 600px)`). Sidebar wird als Drawer mit CSS-Transition ein-/ausgeklappt (class `drawer-open` auf `#app`). Zoom via CSS `transform: scale() translate()` auf einem neuen `#zoom-container`, der Bild + Overlays umschließt — so bleiben Overlay-Positionen automatisch synchron.

**Tech Stack:** Vanilla JS (ES5 pattern wie bestehender Code), CSS Flexbox, kein Build-Tool nötig.

**Spec:** `docs/superpowers/specs/2026-05-12-mobile-responsive-design.md`

---

## File Map

| Datei | Änderung |
|---|---|
| `web/index.html` | Mobile Header, Drawer-Overlay, Zoom-Container, zoom.js einbinden |
| `web/css/style.css` | Zoom-Container-CSS, Mobile-Header-CSS, Media Query Block |
| `web/js/app.js` | Hamburger-Toggle-Logik |
| `web/js/zoom.js` | NEU — Zoom-Logik (Wheel, Pinch, Pan, Reset) |
| `web/js/quiz.js` | `resetZoom()` beim Laden einer neuen Ansicht aufrufen |

---

## Task 1: HTML — Zoom-Container + Mobile-Header + Drawer-Overlay

**Files:**
- Modify: `web/index.html`

Der `#zoom-container` umschließt das Bild und alle Overlays. CSS transform auf diesem Container hält beides synchron. Der Mobile-Header (`#mobile-header`) und das Overlay (`#drawer-overlay`) werden benötigt bevor CSS und JS sie ansprechen können.

- [ ] **Schritt 1: `#zoom-container` in `#quiz-wrapper` einfügen**

  In `web/index.html`, den `#quiz-wrapper`-Inhalt so ändern:

  ```html
  <div id="quiz-wrapper" class="hidden">
      <div id="zoom-container">
          <img id="quiz-img" alt="Anatomie-Bild">
      </div>
  </div>
  ```

  *Hinweis: `quiz.js` hängt `.overlay-group`-Elemente an `wrapper` (= `#quiz-wrapper`) an. Das muss in Task 5 auf `#zoom-container` umgestellt werden.*

- [ ] **Schritt 2: `#mobile-header` vor `#app` einfügen**

  ```html
  <header id="mobile-header">
      <button id="hamburger-btn" aria-label="Menü öffnen">&#9776;</button>
      <span id="mobile-title">Anatomie Lernkarten</span>
      <button id="mobile-help-btn" aria-label="Lösung anzeigen" class="hidden">&#10067;</button>
  </header>
  ```

  Platzierung: direkt vor `<div id="app">`.

- [ ] **Schritt 3: `#drawer-overlay` und `#drawer-close` in `#sidebar` einfügen**

  ```html
  <div id="drawer-overlay"></div>
  ```
  Platzierung: direkt vor `<div id="app">` (nach `#mobile-header`).

  Im `#sidebar` als erstes Kind einen Schließen-Button einfügen:
  ```html
  <nav id="sidebar">
      <button id="drawer-close" aria-label="Menü schließen">&#10005;</button>
      <div id="menu-loading">Lade Menü…</div>
      <ul id="menu-root"></ul>
  </nav>
  ```

- [ ] **Schritt 4: `zoom.js` vor `app.js` einbinden**

  ```html
  <script src="js/levenshtein.js"></script>
  <script src="js/menu.js"></script>
  <script src="js/zoom.js"></script>
  <script src="js/quiz.js"></script>
  <script src="js/app.js"></script>
  ```

- [ ] **Schritt 5: Im Browser prüfen (kein JS-Fehler)**

  Starte einen lokalen Server: `python3 -m http.server 8080` in `web/`  
  Öffne `http://localhost:8080` — die App soll genauso aussehen wie vorher (Desktop unverändert).

- [ ] **Schritt 6: Commit**

  ```bash
  git add web/index.html
  git commit -m "feat: add zoom-container, mobile-header and drawer-overlay to HTML"
  ```

---

## Task 2: CSS — Zoom-Container + Mobile-Header + Media Query

**Files:**
- Modify: `web/css/style.css`

- [ ] **Schritt 1: Zoom-Container CSS hinzufügen (nach `#quiz-wrapper`-Regeln)**

  ```css
  /* ── Zoom container ─────────────────────────── */
  #zoom-container {
      position: relative;
      line-height: 0;
      display: inline-block;
      transform-origin: 0 0;
      will-change: transform;
      cursor: grab;
      touch-action: none;
  }

  #zoom-container.grabbing {
      cursor: grabbing;
  }
  ```

  Gleichzeitig aus `#quiz-wrapper` die Regeln entfernen die jetzt auf `#zoom-container` gehören:
  - `position: relative` und `line-height: 0` und `display: inline-block` von `#quiz-wrapper` auf `#zoom-container` verschieben
  - `#quiz-wrapper` wird zu einem reinen Flexbox-Wrapper:

  ```css
  #quiz-wrapper {
      display: flex;
      align-items: center;
      justify-content: center;
      max-width: 100%;
      max-height: 100%;
      overflow: hidden;
  }
  ```

- [ ] **Schritt 2: Mobile Header CSS hinzufügen (standardmäßig versteckt)**

  ```css
  /* ── Mobile header (nur sichtbar bei ≤ 600px) ─ */
  #mobile-header {
      display: none;
  }

  #drawer-overlay {
      display: none;
  }

  #drawer-close {
      display: none;
  }
  ```

- [ ] **Schritt 3: Media Query Block hinzufügen (am Ende der Datei)**

  ```css
  /* ══════════════════════════════════════════════
     MOBILE  ≤ 600px
  ══════════════════════════════════════════════ */
  @media (max-width: 600px) {

      body {
          overflow: hidden;
      }

      /* Stack layout: header on top, app below */
      body > * {
          /* nothing special needed here */
      }

      #mobile-header {
          display: flex;
          align-items: center;
          height: 48px;
          background: #1a3a6e;
          color: #fff;
          padding: 0 12px;
          gap: 10px;
          flex-shrink: 0;
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 200;
      }

      #hamburger-btn,
      #mobile-help-btn {
          background: none;
          border: none;
          color: #fff;
          font-size: 22px;
          cursor: pointer;
          min-width: 44px;
          min-height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          border-radius: 4px;
          flex-shrink: 0;
      }

      #hamburger-btn:hover,
      #mobile-help-btn:hover {
          background: rgba(255,255,255,0.15);
      }

      #mobile-title {
          flex: 1;
          font-size: 14px;
          font-weight: 600;
          text-align: center;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
      }

      /* Push app content below fixed header */
      #app {
          margin-top: 48px;
          height: calc(100vh - 48px);
      }

      /* ── Drawer ── */
      #drawer-close {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          width: 100%;
          background: none;
          border: none;
          color: #555;
          font-size: 20px;
          cursor: pointer;
          padding: 10px 14px;
          min-height: 44px;
      }

      #drawer-overlay {
          display: block;
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.4);
          z-index: 299;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.3s ease;
      }

      #app.drawer-open #drawer-overlay {
          opacity: 1;
          pointer-events: auto;
      }

      #sidebar {
          position: fixed;
          top: 0;
          left: 0;
          bottom: 0;
          width: 80%;
          min-width: unset;
          max-width: 320px;
          z-index: 300;
          transform: translateX(-100%);
          transition: transform 0.3s ease;
          padding-top: 0;
          box-shadow: 4px 0 20px rgba(0,0,0,0.2);
      }

      #app.drawer-open #sidebar {
          transform: translateX(0);
      }

      /* Bigger touch targets in menu */
      .menu-kat > button {
          min-height: 44px;
          font-size: 16px;
      }

      .menu-unter > button {
          min-height: 44px;
      }

      .menu-ansicht-btn,
      .menu-lernen-btn {
          min-height: 44px;
      }

      /* Main content full width */
      #learn-area {
          width: 100%;
          padding: 8px;
      }

      #quiz-img {
          max-height: calc(100vh - 48px - 16px);
      }
  }
  ```

- [ ] **Schritt 4: Im Browser prüfen**

  Desktop (> 600px): Sidebar wie gewohnt sichtbar, kein Header.  
  DevTools auf 375×667 (iPhone SE): Header sichtbar, Sidebar versteckt, Bild füllt Breite.

- [ ] **Schritt 5: Commit**

  ```bash
  git add web/css/style.css
  git commit -m "feat: add zoom-container CSS and mobile layout with drawer"
  ```

---

## Task 3: JS — Hamburger-Toggle (app.js)

**Files:**
- Modify: `web/js/app.js`

- [ ] **Schritt 1: Hamburger-Toggle-Logik in `app.js` einfügen**

  Nach dem `DOMContentLoaded`-Block (aber noch innerhalb der IIFE) hinzufügen:

  ```js
  // ── Mobile drawer toggle ─────────────────────
  var app = document.getElementById('app');
  var drawerOverlay = document.getElementById('drawer-overlay');
  var hamburgerBtn = document.getElementById('hamburger-btn');
  var drawerCloseBtn = document.getElementById('drawer-close');

  function openDrawer() {
      app.classList.add('drawer-open');
  }

  function closeDrawer() {
      app.classList.remove('drawer-open');
  }

  hamburgerBtn.addEventListener('click', openDrawer);
  drawerCloseBtn.addEventListener('click', closeDrawer);
  drawerOverlay.addEventListener('click', closeDrawer);
  ```

  Das `#mobile-help-btn` im Header soll wie der bestehende Help-Button funktionieren. Da `showHelp()` in `quiz.js` definiert ist, füge in `app.js` hinzu:

  ```js
  var mobileHelpBtn = document.getElementById('mobile-help-btn');
  mobileHelpBtn.addEventListener('click', function () {
      // showHelp() ist in quiz.js definiert und via window.showHelp exponiert (siehe Task 5)
      var activeInput = document.querySelector('.label-input:not(.correct):not([readonly])');
      if (activeInput && typeof window.showHelp === 'function') {
          window.showHelp(activeInput.dataset.solution);
      }
  });
  ```

  *Hinweis: Der `#mobile-help-btn` ist im Header nur sichtbar wenn eine Ansicht geladen ist (wird in Task 5 gesteuert).*

- [ ] **Schritt 2: Drawer schließt sich beim Menü-Klick auf mobile**

  In `menu.js` ist `onSelect` der Callback der aufgerufen wird wenn eine Ansicht gewählt wird. Der Callback kommt aus `app.js` via `buildMenu(data, callback)`. Den `closeDrawer`-Aufruf dort einfügen — nach dem `buildMenu`-Aufruf den Callback wrappen:

  ```js
  buildMenu(data, function (entry, mode) {
      closeDrawer();   // ← hinzufügen
      if (mode === 'lernen') {
          loadLernen(entry, OG_IMG_BASE);
      } else {
          loadQuiz(entry, IMG_BASE);
      }
  });
  ```

- [ ] **Schritt 3: Im Browser prüfen (DevTools 375px)**

  ☰ öffnet Drawer, ✕ schließt, Overlay-Klick schließt, Menü-Eintrag wählen schließt Drawer.

- [ ] **Schritt 4: Commit**

  ```bash
  git add web/js/app.js
  git commit -m "feat: hamburger menu toggle for mobile drawer"
  ```

---

## Task 4: JS — Zoom-Feature (zoom.js)

**Files:**
- Create: `web/js/zoom.js`

Die Zoom-Logik folgt dem Muster `transform: translate(tx, ty) scale(s)` mit `transform-origin: 0 0`. Die Mathe:

- Zoom auf Cursor-/Pinch-Mittelpunkt `(cx, cy)` relativ zum Container:
  - Punkt in Content-Space: `px = (cx - tx) / s`
  - Nach Scale-Änderung: `newTx = cx - px * newS`
- Pan-Clamping: `tx` zwischen `containerW - s*contentW` und `0`

- [ ] **Schritt 1: `zoom.js` erstellen**

  ```js
  (function () {
      var ZOOM_MIN = 1.0;
      var ZOOM_MAX = 4.0;
      var ZOOM_STEP = 0.12;        // pro Scrollrad-Klick
      var TAP_MAX_MOVE = 10;       // px — darunter gilt Touch als Tap, nicht Pan
      var DOUBLE_TAP_MS = 300;

      var container = null;
      var state = { s: 1, tx: 0, ty: 0 };
      var lastTapTime = 0;

      // touch tracking
      var touch1 = null, touch2 = null;
      var panStart = null;         // { x, y, tx, ty }
      var pinchStartDist = null;
      var pinchStartState = null;  // { s, tx, ty }
      var touchMoved = false;

      function applyTransform() {
          container.style.transform =
              'translate(' + state.tx + 'px, ' + state.ty + 'px) scale(' + state.s + ')';
      }

      function clamp(val, min, max) {
          return Math.max(min, Math.min(max, val));
      }

      function clampState() {
          if (state.s <= 1) {
              state.tx = 0;
              state.ty = 0;
              state.s = 1;
              return;
          }
          var rect = container.parentElement.getBoundingClientRect();
          var cw = container.offsetWidth;
          var ch = container.offsetHeight;
          state.tx = clamp(state.tx, rect.width  - state.s * cw, 0);
          state.ty = clamp(state.ty, rect.height - state.s * ch, 0);
      }

      function zoomAt(cx, cy, newS) {
          newS = clamp(newS, ZOOM_MIN, ZOOM_MAX);
          var px = (cx - state.tx) / state.s;
          var py = (cy - state.ty) / state.s;
          state.tx = cx - px * newS;
          state.ty = cy - py * newS;
          state.s  = newS;
          clampState();
          applyTransform();
      }

      function resetZoom() {
          state.s  = 1;
          state.tx = 0;
          state.ty = 0;
          if (container) applyTransform();
      }

      // ── Mouse wheel ────────────────────────────
      function onWheel(e) {
          e.preventDefault();
          var rect = container.getBoundingClientRect();
          var cx = e.clientX - rect.left - state.tx;
          var cy = e.clientY - rect.top  - state.ty;
          // Koordinaten relativ zur linken oberen Ecke des (untransformierten) Containers
          var cx2 = e.clientX - container.parentElement.getBoundingClientRect().left;
          var cy2 = e.clientY - container.parentElement.getBoundingClientRect().top;
          var delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
          zoomAt(cx2, cy2, state.s + delta);
      }

      // ── Touch helpers ──────────────────────────
      function getTouchDist(a, b) {
          var dx = a.clientX - b.clientX;
          var dy = a.clientY - b.clientY;
          return Math.sqrt(dx * dx + dy * dy);
      }

      function getTouchMid(a, b) {
          var rect = container.parentElement.getBoundingClientRect();
          return {
              x: (a.clientX + b.clientX) / 2 - rect.left,
              y: (a.clientY + b.clientY) / 2 - rect.top
          };
      }

      function onTouchStart(e) {
          touchMoved = false;
          if (e.touches.length === 1) {
              touch1 = e.touches[0];
              touch2 = null;
              var rect = container.parentElement.getBoundingClientRect();
              panStart = {
                  x: touch1.clientX - rect.left,
                  y: touch1.clientY - rect.top,
                  tx: state.tx,
                  ty: state.ty
              };
              // Double-tap check
              var now = Date.now();
              if (now - lastTapTime < DOUBLE_TAP_MS) {
                  e.preventDefault();
                  resetZoom();
                  applyTransform();
              }
              lastTapTime = now;
          } else if (e.touches.length === 2) {
              e.preventDefault();
              touch1 = e.touches[0];
              touch2 = e.touches[1];
              pinchStartDist  = getTouchDist(touch1, touch2);
              pinchStartState = { s: state.s, tx: state.tx, ty: state.ty };
              panStart = null;
          }
      }

      function onTouchMove(e) {
          if (e.touches.length === 2 && pinchStartDist !== null) {
              e.preventDefault();
              touch1 = e.touches[0];
              touch2 = e.touches[1];
              var dist = getTouchDist(touch1, touch2);
              var mid  = getTouchMid(touch1, touch2);
              var newS = clamp(pinchStartState.s * (dist / pinchStartDist), ZOOM_MIN, ZOOM_MAX);
              // Zoom um den Pinch-Mittelpunkt
              var px = (mid.x - pinchStartState.tx) / pinchStartState.s;
              var py = (mid.y - pinchStartState.ty) / pinchStartState.s;
              state.s  = newS;
              state.tx = mid.x - px * newS;
              state.ty = mid.y - py * newS;
              clampState();
              applyTransform();
              touchMoved = true;
          } else if (e.touches.length === 1 && panStart !== null && state.s > 1) {
              // Nur panning wenn gezoomt
              var t = e.touches[0];
              var rect = container.parentElement.getBoundingClientRect();
              var dx = (t.clientX - rect.left) - panStart.x;
              var dy = (t.clientY - rect.top)  - panStart.y;
              if (Math.abs(dx) > TAP_MAX_MOVE || Math.abs(dy) > TAP_MAX_MOVE) {
                  e.preventDefault();
                  touchMoved = true;
                  state.tx = panStart.tx + dx;
                  state.ty = panStart.ty + dy;
                  clampState();
                  applyTransform();
                  container.classList.add('grabbing');
              }
          }
      }

      function onTouchEnd(e) {
          if (e.touches.length < 2) {
              pinchStartDist  = null;
              pinchStartState = null;
          }
          if (e.touches.length === 0) {
              touch1 = null;
              touch2 = null;
              panStart = null;
              container.classList.remove('grabbing');
          }
      }

      // ── Mouse drag pan ─────────────────────────
      var mousePanStart = null;

      function onMouseDown(e) {
          if (state.s <= 1) return;
          mousePanStart = { x: e.clientX, y: e.clientY, tx: state.tx, ty: state.ty };
          container.classList.add('grabbing');
      }

      function onMouseMove(e) {
          if (!mousePanStart) return;
          state.tx = mousePanStart.tx + (e.clientX - mousePanStart.x);
          state.ty = mousePanStart.ty + (e.clientY - mousePanStart.y);
          clampState();
          applyTransform();
      }

      function onMouseUp() {
          mousePanStart = null;
          container.classList.remove('grabbing');
      }

      // ── Public API ─────────────────────────────
      window.resetZoom = resetZoom;

      function initZoom(el) {
          container = el;
          container.style.transformOrigin = '0 0';

          container.addEventListener('wheel', onWheel, { passive: false });
          container.addEventListener('touchstart', onTouchStart, { passive: false });
          container.addEventListener('touchmove',  onTouchMove,  { passive: false });
          container.addEventListener('touchend',   onTouchEnd,   { passive: false });
          container.addEventListener('mousedown',  onMouseDown);
          document.addEventListener('mousemove',   onMouseMove);
          document.addEventListener('mouseup',     onMouseUp);
      }

      window.initZoom = initZoom;
  }());
  ```

- [ ] **Schritt 2: Im Browser prüfen**

  Nach Task 5 (Wire-up) testbar. Vorerst prüfen ob `zoom.js` ohne Syntaxfehler lädt: DevTools Console — kein Fehler.

- [ ] **Schritt 3: Commit**

  ```bash
  git add web/js/zoom.js
  git commit -m "feat: zoom.js — scroll wheel, pinch-to-zoom, pan and double-tap reset"
  ```

---

## Task 5: Wire-up — Zoom in quiz.js initialisieren + Overlays auf zoom-container

**Files:**
- Modify: `web/js/quiz.js`

Aktuell hängt `renderOverlays()` die `.overlay-group`-Elemente an `wrapper` (`#quiz-wrapper`) an. Sie müssen stattdessen an `#zoom-container` angehängt werden, damit sie mit skaliert werden.

- [ ] **Schritt 1: Overlay-Ziel von `wrapper` auf `zoomContainer` umstellen**

  In `loadLernen`, `loadQuiz` und `renderOverlays` alle `wrapper`-Referenzen für Overlays auf `zoomContainer` umstellen.

  Am Anfang der Datei `quiz.js` nach den var-Deklarationen:

  ```js
  var _zoomContainer = null;
  ```

  In `loadLernen`:
  ```js
  function loadLernen(entry, ogImgBasePath) {
      _currentEntry = null;

      var img = document.getElementById('quiz-img');
      var wrapper = document.getElementById('quiz-wrapper');
      var zoomContainer = document.getElementById('zoom-container');  // ← neu
      var placeholder = document.getElementById('placeholder');

      img.onload = null;
      zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });  // ← war wrapper

      placeholder.classList.add('hidden');
      wrapper.classList.remove('hidden');
      resetZoom();  // ← neu: Zoom zurücksetzen bei neuer Ansicht

      img.src = ogImgBasePath + entry.og_filename;
  }
  ```

  In `loadQuiz`:
  ```js
  function loadQuiz(entry, imgBasePath) {
      _currentEntry = entry;
      _imgBasePath = imgBasePath;

      var img = document.getElementById('quiz-img');
      var wrapper = document.getElementById('quiz-wrapper');
      var zoomContainer = document.getElementById('zoom-container');  // ← neu
      var placeholder = document.getElementById('placeholder');

      zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });  // ← war wrapper

      placeholder.classList.add('hidden');
      wrapper.classList.remove('hidden');
      resetZoom();  // ← neu

      img.onload = function () {
          renderOverlays(entry.labels, img, zoomContainer);  // ← war wrapper
      };
      img.src = imgBasePath + entry.filename;
      if (img.complete && img.naturalWidth > 0) {
          renderOverlays(entry.labels, img, zoomContainer);  // ← war wrapper
      }
  }
  ```

  In `renderOverlays`: Parameter heißt weiterhin `wrapper` aber erhält jetzt `zoomContainer`. Kein Umbenennen nötig — der Parameter-Name ist intern.

  Im Resize-Handler, `wrapper`-Referenz aktualisieren:
  ```js
  window.addEventListener('resize', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(function () {
          if (!_currentEntry) return;
          var img = document.getElementById('quiz-img');
          var zoomContainer = document.getElementById('zoom-container');  // ← war wrapper

          var state = {};
          zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
              state[inp.dataset.ox + ',' + inp.dataset.oy] = {
                  value: inp.value,
                  className: inp.className,
                  bgStyle: inp.style.background,
                  readOnly: inp.readOnly
              };
          });

          renderOverlays(_currentEntry.labels, img, zoomContainer);  // ← war wrapper

          zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
              var key = inp.dataset.ox + ',' + inp.dataset.oy;
              if (state[key]) {
                  inp.value = state[key].value;
                  inp.className = state[key].className;
                  inp.style.background = state[key].bgStyle;
                  inp.readOnly = state[key].readOnly;
              }
          });
      }, 120);
  });
  ```

- [ ] **Schritt 2: `showHelp` global exponieren + `initZoom` aufrufen**

  Am Ende von `quiz.js` (nach dem Resize-Handler) hinzufügen:

  ```js
  // showHelp global verfügbar machen (für mobile-help-btn in app.js)
  window.showHelp = showHelp;

  // ── Zoom initialisieren ──────────────────────
  document.addEventListener('DOMContentLoaded', function () {
      initZoom(document.getElementById('zoom-container'));
  });
  ```

- [ ] **Schritt 3: Vollständige Verifikation im Browser**

  **Desktop:**
  - Sidebar sichtbar, kein Mobile-Header ✓
  - Scrollrad über dem Bild → Bild + Overlays zoomen synchron ✓
  - Maus-Drag nach Zoom → Bild verschiebt sich, Overlays bleiben auf Positionen ✓
  - Neue Ansicht wählen → Zoom resettet auf 1× ✓

  **DevTools Mobile (375×667, Touch-Simulation):**
  - Mobile-Header sichtbar (☰, Titel, ❓) ✓
  - ☰ öffnet Drawer von links ✓
  - Overlay-Klick schließt Drawer ✓
  - ✕-Button schließt Drawer ✓
  - Menü-Eintrag wählen → Drawer schließt, Bild wird geladen ✓
  - Pinch-Zoom (Two-Finger in DevTools): Bild + Overlays zoomen ✓
  - Ein-Finger-Drag nach Zoom: Bild verschiebt sich ✓
  - Doppeltipp: Zoom zurückgesetzt ✓
  - Eingabe in `.label-input` noch möglich (kein Tap wird als Pan gewertet) ✓

- [ ] **Schritt 4: Commit**

  ```bash
  git add web/js/quiz.js
  git commit -m "feat: wire zoom into quiz — overlays on zoom-container, resetZoom on load"
  ```

---

## Task 6: Mobile-Title im Header aktualisieren

**Files:**
- Modify: `web/js/app.js`

Der `#mobile-title` soll die aktuelle Ansicht anzeigen (z. B. „Schulter – Anterior") sobald eine Ansicht geladen wird.

- [ ] **Schritt 1: Title-Update in den Lade-Callback einbauen**

  In `app.js` im `buildMenu`-Callback:

  `data.json` hat kein `label`-Feld — nur `filename` und `og_filename`. Den Titel aus `entry.filename` ableiten (Extension entfernen, Bindestriche durch Leerzeichen ersetzen):

  ```js
  buildMenu(data, function (entry, mode) {
      closeDrawer();
      // Titel aus filename ableiten (z. B. "schulter-anterior.jpg" → "schulter anterior")
      var mobileTitle = document.getElementById('mobile-title');
      var rawName = (entry.filename || '').replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ');
      mobileTitle.textContent = rawName || 'Anatomie Lernkarten';
      // Zeige mobile help button nur im Quiz-Modus
      var mobileHelpBtn = document.getElementById('mobile-help-btn');
      mobileHelpBtn.classList.toggle('hidden', mode === 'lernen');

      if (mode === 'lernen') {
          loadLernen(entry, OG_IMG_BASE);
      } else {
          loadQuiz(entry, IMG_BASE);
      }
  });
  ```

- [ ] **Schritt 2: Verifikation**

  Mobile-Ansicht: Ansicht wählen → Header-Titel aktualisiert sich, ❓ sichtbar im Quiz-Modus, versteckt im Lern-Modus.

- [ ] **Schritt 3: Commit**

  ```bash
  git add web/js/app.js
  git commit -m "feat: update mobile header title and show help-btn on quiz mode"
  ```
