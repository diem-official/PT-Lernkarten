(function () {
    var DATA_URL      = 'data/data.json';
    var TEXT_DATA_URL = 'data/text-data.json';
    var IMG_BASE      = 'data/images/';
    var OG_IMG_BASE   = 'data/og-images/';

    function showError(msg) {
        var loading = document.getElementById('menu-loading');
        loading.textContent = 'Fehler: ' + msg;
        loading.style.color = '#c00';
    }

    // ── Mobile drawer toggle ─────────────────────
    var app = document.getElementById('app');
    var drawerOverlay = document.getElementById('drawer-overlay');
    var hamburgerBtn = document.getElementById('hamburger-btn');
    var drawerCloseBtn = document.getElementById('drawer-close');
    var mobileTitle = document.getElementById('mobile-title');

    function openDrawer() {
        app.classList.add('drawer-open');
    }

    function closeDrawer() {
        app.classList.remove('drawer-open');
    }

    hamburgerBtn.addEventListener('click', openDrawer);
    drawerCloseBtn.addEventListener('click', closeDrawer);
    drawerOverlay.addEventListener('click', closeDrawer);

    // ── Visual-viewport: Bild beim Öffnen der Tastatur nach oben schieben ──
    var imgEl = document.getElementById('quiz-img');
    function onViewportResize() {
        if (window.innerWidth > 600) return;
        var available = Math.round(window.visualViewport.height) - 48;
        app.style.height      = available + 'px';
        imgEl.style.maxHeight = available + 'px';
        window.dispatchEvent(new Event('resize')); // Overlays neu positionieren
    }
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', onViewportResize);
    }

    document.addEventListener('DOMContentLoaded', function () {
        Promise.all([
            fetch(DATA_URL).then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            }),
            fetch(TEXT_DATA_URL).then(function (resp) {
                return resp.ok ? resp.json() : [];
            }).catch(function () { return []; })
        ])
        .then(function (results) {
            var imageData = results[0];
            var textData  = results[1];
            var allData   = imageData.concat(textData);

            if (!allData.length) {
                showError('Keine Daten gefunden (data.json und text-data.json sind leer oder fehlen).');
                return;
            }

            buildMenu(allData, function (entry, mode) {
                closeDrawer();
                mobileTitle.textContent = entry.subject + ' – ' + entry.subcategory + ' – ' + entry.view;

                if (entry.type === 'text') {
                    loadTextQuiz(entry);
                } else {
                    if (mode === 'lernen') {
                        loadLernen(entry, OG_IMG_BASE);
                    } else {
                        loadQuiz(entry, IMG_BASE);
                    }
                }
            });
        })
        .catch(function (err) {
            showError(err.message + ' – Starte einen lokalen Webserver (z. B. python3 -m http.server 8080)');
        });
    });
}());
