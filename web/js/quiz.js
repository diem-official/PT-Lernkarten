var _currentEntry = null;
var _imgBasePath = '';
var _resizeTimer = null;

function loadLernen(entry, ogImgBasePath) {
    _currentEntry = null;

    var img = document.getElementById('quiz-img');
    var wrapper = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder = document.getElementById('placeholder');

    img.onload = null;
    zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    img.src = ogImgBasePath + entry.og_filename;
}

function loadQuiz(entry, imgBasePath) {
    _currentEntry = entry;
    _imgBasePath = imgBasePath;

    var img = document.getElementById('quiz-img');
    var wrapper = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder = document.getElementById('placeholder');

    zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    img.onload = function () {
        renderOverlays(entry.labels, img, zoomContainer);
    };
    img.src = imgBasePath + entry.filename;
    // If the browser already has this image cached (same URL), onload won't fire.
    // Call renderOverlays directly when the image is already complete.
    if (img.complete && img.naturalWidth > 0) {
        renderOverlays(entry.labels, img, zoomContainer);
    }
}

function renderOverlays(labels, img, wrapper) {
    // Remove stale overlays
    wrapper.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    var scaleX = img.clientWidth / img.naturalWidth;
    var scaleY = img.clientHeight / img.naturalHeight;

    labels.forEach(function (label) {
        var group = document.createElement('div');
        group.className = 'overlay-group';
        group.style.left = (label.mask_box.x * scaleX) + 'px';
        group.style.top = (label.mask_box.y * scaleY) + 'px';

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'label-input';
        input.style.width = (label.mask_box.w * scaleX) + 'px';
        input.dataset.solution = label.text;
        // Store original coords so we can restore state after resize
        input.dataset.ox = label.anchor_x;
        input.dataset.oy = label.anchor_y;

        var helpBtn = document.createElement('button');
        helpBtn.type = 'button';
        helpBtn.className = 'help-btn';
        helpBtn.textContent = '?';
        helpBtn.setAttribute('aria-label', 'Lösung anzeigen');

        (function (inp, solution) {
            inp.addEventListener('input', function () { onInputChange(inp); });
            helpBtn.addEventListener('click', function () { showHelp(solution); });
        }(input, label.text));

        group.appendChild(input);
        group.appendChild(helpBtn);
        wrapper.appendChild(group);
    });
}

function onInputChange(input) {
    if (input.readOnly) return;

    var value = input.value;
    var solution = input.dataset.solution;

    if (value.length === 0) {
        input.className = 'label-input';
        input.style.background = '';
        return;
    }

    var isPrefix = solution.toLowerCase().startsWith(value.toLowerCase());

    if (!isPrefix) {
        input.className = 'label-input typo';
        input.style.background = '';
    } else if (value.length === solution.length) {
        input.style.background = '';
        input.className = 'label-input correct';
        input.readOnly = true;
    } else {
        var alpha = (value.length / solution.length).toFixed(2);
        input.style.background = 'rgba(80, 200, 100, ' + alpha + ')';
        input.className = 'label-input';
    }
}

// ── Help modal ───────────────────────────────────────────────────────────────

function showHelp(solution) {
    document.getElementById('modal-solution').textContent = solution;
    document.getElementById('help-modal').classList.remove('hidden');
    document.getElementById('modal-close').focus();
}

document.getElementById('modal-close').addEventListener('click', function () {
    document.getElementById('help-modal').classList.add('hidden');
});

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        document.getElementById('help-modal').classList.add('hidden');
    }
});

// showHelp global verfügbar machen (für mobile-help-btn in app.js)
window.showHelp = showHelp;

// ── Resize handler (debounced) ───────────────────────────────────────────────

window.addEventListener('resize', function () {
    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(function () {
        if (!_currentEntry) return;
        var img = document.getElementById('quiz-img');
        var zoomContainer = document.getElementById('zoom-container');

        // Capture current input state keyed by original coords
        var savedState = {};
        zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
            savedState[inp.dataset.ox + ',' + inp.dataset.oy] = {
                value: inp.value,
                className: inp.className,
                bgStyle: inp.style.background,
                readOnly: inp.readOnly
            };
        });

        renderOverlays(_currentEntry.labels, img, zoomContainer);

        // Restore state
        zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
            var key = inp.dataset.ox + ',' + inp.dataset.oy;
            if (savedState[key]) {
                inp.value = savedState[key].value;
                inp.className = savedState[key].className;
                inp.style.background = savedState[key].bgStyle;
                inp.readOnly = savedState[key].readOnly;
            }
        });
    }, 120);
});

// ── Zoom initialisieren ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'));
});
