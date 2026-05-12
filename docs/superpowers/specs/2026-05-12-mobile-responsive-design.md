# Mobile Responsive Design — Anatomie Lernkarten

**Date:** 2026-05-12  
**Status:** Approved

## Kontext

Die App ist aktuell rein Desktop-optimiert: eine feste Sidebar (22% Breite), kleine Eingabefelder direkt auf dem Bild, keine Media Queries. Auf Smartphones im Hochkantformat (≤ 600px) ist die App kaum nutzbar. Ziel ist ein vollständig mobil-nutzbares Layout — ohne das Desktop-Verhalten zu verändern.

---

## Entscheidungen aus dem Design-Prozess

| Thema | Entscheidung |
|---|---|
| Sidebar auf Mobile | Standardmäßig versteckt, per Hamburger-Menü öffenbar |
| Menü-Öffnen | Slide-in Drawer von links (~70% Breite), Overlay dahinter |
| Quiz-Eingabefelder | Bleiben auf dem Bild (wie bisher), skalieren mit |
| Zoom | Scrollrad (Maus) + Pinch-to-Zoom (Touch) + Pan, 1×–4× |

---

## Breakpoint

`@media (max-width: 600px)` — greift auf Smartphones im Hochkantformat.

---

## Layout-Änderungen (Mobile)

### Header-Leiste (neu, nur mobile)
- Feste Höhe: 48px
- Links: ☰ Hamburger-Button
- Mitte: Aktuelle Ansicht (z. B. „Schulter – Anterior")
- Rechts: ❓ Hilfe-Button
- Hintergrundfarbe: `#1a3a6e` (wie bestehende Akzentfarbe)

### Sidebar
- Standardmäßig ausgeblendet: `transform: translateX(-100%)`
- Beim Öffnen: `transform: translateX(0)`, Transition `300ms ease`
- Breite: 80% des Viewports, max. 320px
- Overlay: `rgba(0,0,0,0.4)` hinter dem Drawer, Tippen schließt
- Schließen: ✕-Button im Drawer oben rechts oder Overlay-Tippen
- Touch-Ziele: alle Menü-Buttons min. 44px Höhe

### Hauptbereich
- Nimmt volle Viewport-Breite ein
- Bild zentriert, `max-height: calc(100vh - 48px)` (Header-Höhe abziehen)

---

## Zoom-Feature (Desktop & Mobile)

### Container-Struktur
```
#learn-area
  └── #zoom-container   ← neu: CSS transform: scale() hier
        └── img#main-image
        └── .overlay-inputs (absolut positioniert)
```

### Warum CSS transform?
`quiz.js` berechnet Overlay-Positionen über `img.clientWidth / img.naturalWidth`. CSS `transform: scale()` verändert `clientWidth` nicht — Overlays bleiben ohne Umbau korrekt positioniert.

### Maus (Scrollrad)
- Event: `wheel` auf `#zoom-container`
- Zoom-Schritt: 0.1 pro Scroll-Tick
- Zoom-Zentrum: Mauszeiger-Position (`transform-origin` dynamisch setzen)
- `e.preventDefault()` verhindert Seiten-Scroll während Zoom

### Touch (Pinch + Pan)
- Events: `touchstart`, `touchmove`, `touchend`
- Pinch: Distanz zwischen zwei Fingern berechnen → Skalierung
- Pan: Ein-Finger-Drag verschiebt den Container (translateX/Y)
- `touch-action: none` am Container (verhindert Browser-native-Zoom dort)

### Zoom-Bereich & Reset
- Min: 1.0 (kein Herauszoomen)
- Max: 4.0
- Doppeltipp (< 300ms zwischen zwei Taps): Reset auf 1×, translate(0,0)
- Pan wird auf Bildgrenzen geclampt, damit das Bild nicht komplett aus dem Sichtfeld gleitet

### State
```js
let zoomState = { scale: 1.0, tx: 0, ty: 0 };
```
Wird bei `renderOverlays()` (Resize-Event) zurückgesetzt.

---

## Dateien die sich ändern

| Datei | Änderung |
|---|---|
| `web/index.html` | Mobile Header-Leiste + Hamburger-Button + Drawer-Overlay einfügen |
| `web/css/style.css` | `@media (max-width: 600px)` Block + Zoom-Container-CSS + Drawer-Animation |
| `web/js/app.js` | Hamburger-Toggle-Logik (open/close Drawer) |
| `web/js/quiz.js` | Zoom-Container initialisieren, Wheel + Touch Events, Pan-Clamping |

---

## Verifikation

1. Desktop (> 600px): Kein visueller Unterschied — Sidebar bleibt sichtbar, kein Header
2. Mobile Chrome DevTools (375×667, iPhone SE): Hamburger sichtbar, Sidebar öffnet/schließt korrekt
3. Zoom Maus: Scrollrad zoomt Bild + Overlays synchron
4. Zoom Touch (DevTools touch simulation): Pinch zoomt, ein-Finger-Drag verschiebt
5. Doppeltipp setzt Zoom zurück
6. Quiz-Felder bleiben korrekt positioniert während/nach Zoom
7. Hilfe-Modal öffnet korrekt auf Mobile
