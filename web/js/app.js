(function () {
    var DATA_URL = 'data/data.json';
    var IMG_BASE = 'data/images/';
    var OG_IMG_BASE = 'data/og-images/';

    function showError(msg) {
        var loading = document.getElementById('menu-loading');
        loading.textContent = 'Fehler: ' + msg;
        loading.style.color = '#c00';
    }

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
