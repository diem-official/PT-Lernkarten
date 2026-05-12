(function () {
    var DATA_URL = 'data/data.json';
    var IMG_BASE = 'data/images/';
    var OG_IMG_BASE = 'data/og-images/';

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
    var mobileHelpBtn = document.getElementById('mobile-help-btn');

    function openDrawer() {
        app.classList.add('drawer-open');
    }

    function closeDrawer() {
        app.classList.remove('drawer-open');
    }

    hamburgerBtn.addEventListener('click', openDrawer);
    drawerCloseBtn.addEventListener('click', closeDrawer);
    drawerOverlay.addEventListener('click', closeDrawer);

    mobileHelpBtn.addEventListener('click', function () {
        var activeInput = document.querySelector('.label-input:not(.correct):not([readonly])');
        if (activeInput && typeof window.showHelp === 'function') {
            window.showHelp(activeInput.dataset.solution);
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        fetch(DATA_URL)
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (data) {
                if (!data.length) {
                    showError('data.json ist leer.');
                    return;
                }
                buildMenu(data, function (entry, mode) {
                    closeDrawer();
                    var rawName = (entry.filename || '').replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ');
                    mobileTitle.textContent = rawName || 'Anatomie Lernkarten';
                    mobileHelpBtn.classList.toggle('hidden', mode === 'lernen');

                    if (mode === 'lernen') {
                        loadLernen(entry, OG_IMG_BASE);
                    } else {
                        loadQuiz(entry, IMG_BASE);
                    }
                });
            })
            .catch(function (err) {
                showError(err.message + ' – Starte einen lokalen Webserver (z. B. python3 -m http.server 8080)');
            });
    });
}());
