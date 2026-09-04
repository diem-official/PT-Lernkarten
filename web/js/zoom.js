(function () {
    var ZOOM_MIN = 1.0;
    var ZOOM_MAX = 4.0;
    var ZOOM_STEP = 0.12;
    var TAP_MAX_MOVE = 10;
    var DOUBLE_TAP_MS = 300;

    window.createZoom = function (el) {
        var container = el;
        var state = { s: 1, tx: 0, ty: 0 };
        var lastTapTime = 0;

        var touch1 = null, touch2 = null;
        var panStart = null;
        var pinchStartDist = null;
        var pinchStartState = null;
        var mousePanStart = null;

        function applyTransform() {
            container.style.transform =
                'translate(' + state.tx + 'px, ' + state.ty + 'px) scale(' + state.s + ')';
        }

        function clamp(val, min, max) {
            return Math.max(min, Math.min(max, val));
        }

        // #zoom-container is flexbox-centered inside its parent.
        // state.tx/ty are *additional* translation on top of that centering offset.
        // This returns how far the container's natural (untransformed) left/top edge
        // sits from the wrapper's left/top edge.
        function getNaturalOffset() {
            var rect = container.parentElement.getBoundingClientRect();
            return {
                x: (rect.width  - container.offsetWidth)  / 2,
                y: (rect.height - container.offsetHeight) / 2
            };
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
            var ox = (rect.width  - cw) / 2;
            var oy = (rect.height - ch) / 2;

            // Clamp so no empty gap appears at any wrapper edge.
            var txA = -ox,                           txB = rect.width  - state.s * cw - ox;
            var tyA = -oy,                           tyB = rect.height - state.s * ch - oy;
            state.tx = clamp(state.tx, Math.min(txA, txB), Math.max(txA, txB));
            state.ty = clamp(state.ty, Math.min(tyA, tyB), Math.max(tyA, tyB));
        }

        function zoomAt(cx, cy, newS) {
            newS = clamp(newS, ZOOM_MIN, ZOOM_MAX);
            var off = getNaturalOffset();
            var px = (cx - off.x - state.tx) / state.s;
            var py = (cy - off.y - state.ty) / state.s;
            state.tx = cx - off.x - px * newS;
            state.ty = cy - off.y - py * newS;
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

        // ── Mouse wheel ────────────────────────────────────────────────────────
        function onWheel(e) {
            e.preventDefault();
            var rect = container.parentElement.getBoundingClientRect();
            var cx = e.clientX - rect.left;
            var cy = e.clientY - rect.top;
            var delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
            zoomAt(cx, cy, state.s + delta);
        }

        // ── Touch helpers ──────────────────────────────────────────────────────
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
                var now = Date.now();
                if (now - lastTapTime < DOUBLE_TAP_MS) {
                    e.preventDefault();
                    resetZoom();
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
                var off  = getNaturalOffset();
                var px = (mid.x - off.x - pinchStartState.tx) / pinchStartState.s;
                var py = (mid.y - off.y - pinchStartState.ty) / pinchStartState.s;
                state.s  = newS;
                state.tx = mid.x - off.x - px * newS;
                state.ty = mid.y - off.y - py * newS;
                clampState();
                applyTransform();
            } else if (e.touches.length === 1 && panStart !== null && state.s > 1) {
                var t = e.touches[0];
                var rect = container.parentElement.getBoundingClientRect();
                var dx = (t.clientX - rect.left) - panStart.x;
                var dy = (t.clientY - rect.top)  - panStart.y;
                if (Math.abs(dx) > TAP_MAX_MOVE || Math.abs(dy) > TAP_MAX_MOVE) {
                    e.preventDefault();
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

        // ── Mouse drag pan ─────────────────────────────────────────────────────
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

        container.style.transformOrigin = '0 0';
        container.addEventListener('wheel',      onWheel,      { passive: false });
        container.addEventListener('touchstart', onTouchStart, { passive: false });
        container.addEventListener('touchmove',  onTouchMove,  { passive: false });
        container.addEventListener('touchend',   onTouchEnd,   { passive: false });
        container.addEventListener('mousedown',  onMouseDown);
        document.addEventListener('mousemove',   onMouseMove);
        document.addEventListener('mouseup',     onMouseUp);

        var resizeTimer = null;
        function onResize() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                clampState();
                applyTransform();
            }, 50);
        }
        window.addEventListener('resize', onResize);

        return { reset: resetZoom };
    };

    // Backwards-compatible wrapper for the image quiz.
    window.initZoom = function (el) {
        var instance = window.createZoom(el);
        window.resetZoom = instance.reset;
    };

    // Hält die Bild(er) in `pane` (#image-pane oder .tq-quiz-image-pane) auf
    // dessen tatsächliche Höhe begrenzt (Orientation-Wechsel, Resize,
    // Größenänderung des Nachbar-Panels — alles über ResizeObserver auf
    // `pane` selbst statt einzelner Event-Quellen).
    //
    // Setzt dazu style.maxHeight direkt als Pixelwert statt eines CSS-%-
    // max-height, weil der direkte Elternteil des <img> (#zoom-container
    // bzw. .tq-dual-image-container) keine definite Höhe hat, an der ein
    // Prozentwert sich verankern könnte — und weil eine CSS-Variable
    // (var(--pane-max-h, …)) als Zwischenlösung im vollen App-Kontext bei
    // wiederholten Orientation-Wechseln beobachtbar hängen blieb (nach
    // Portrait→Landscape→Portrait behielt max-height den dvh-Fallback statt
    // der aktuellen Variable — reproduzierbar nur im vollen Bundle, nicht in
    // einer Minimal-Reduktion; vermutlich eine Style-Invalidierungs-
    // Eigenheit des Browsers rund um var() zusammen mit dvh-Fallbacks).
    // Eine direkte Inline-Zuweisung ist robust dagegen, da sie bei jedem
    // ResizeObserver-Tick frisch gesetzt wird, ohne über var()-Auflösung zu
    // laufen.
    //
    // Bei zwei Bildern (.tq-dual-image-container) unterscheidet sich die
    // Aufteilung je nach Layout: in der Reihe (>= 600px, siehe style.css)
    // bekommt jedes Bild einzeln die volle Pane-Höhe als max-height; gestapelt
    // (< 600px, flex-direction:column) bekommt stattdessen der Container
    // selbst eine definite Höhe, und flex:1 1 0 (siehe style.css) teilt sie
    // automatisch auf beide Bilder auf — ein max-height pro Bild würde dort
    // nicht wissen, dass es sich die Höhe mit einem zweiten Bild teilen muss.
    window.syncPaneHeight = function (pane) {
        if (!pane || pane._paneHeightBound) return;
        pane._paneHeightBound = true;

        function sync() {
            var h = pane.clientHeight;
            var dualCont = pane.querySelector('.tq-dual-image-container');
            var stacked = dualCont && getComputedStyle(dualCont).flexDirection === 'column';

            if (dualCont) {
                dualCont.style.height = stacked ? h + 'px' : '';
            }
            pane.querySelectorAll('img').forEach(function (img) {
                img.style.maxHeight = stacked ? '' : h + 'px';
            });
        }
        sync();

        if (window.ResizeObserver) {
            new ResizeObserver(sync).observe(pane);
        } else {
            window.addEventListener('resize', sync);
        }
    };
}());
