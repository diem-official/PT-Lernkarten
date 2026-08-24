// ── Text quiz: "Quiz" mode ───────────────────────────────────────────────────
// Analog zum Bild-Quiz-Abfrage-Modus (quiz-abfrage.js): fragt (Zeile, Spalte)-
// Paare einzeln ab, mit Selbsteinschätzung (Korrekt/Falsch) statt Texteingabe.
// Nutzt eine eigene Datenquelle (text-quiz-data.json) mit ausführlicheren
// Antworten als text-data.json (das weiterhin für Lernen/Schreiben verwendet wird).

function loadTextQuizAbfrage(entry, imgBase, textQuizData) {
    _activeMarkerRefresh = null;
    // Text-Modi rendern in #text-quiz-wrapper, NICHT in #answer-panel — das ist
    // DOM-Kind von #quiz-wrapper, welches _textWrapperSetup() versteckt bleibt.
    var textWrapper = _textWrapperSetup();

    var quizEntry = _tqFindQuizEntry(entry, textQuizData);

    if (!quizEntry) {
        var panel = document.createElement('div');
        panel.className = 'qz-panel';
        var msg = document.createElement('p');
        msg.className   = 'qz-heading';
        msg.textContent = 'Noch keine Quiz-Daten für diese Ansicht vorhanden.';
        panel.appendChild(msg);
        textWrapper.appendChild(panel);
        return;
    }

    // Mit Bild: Bild links, Panel rechts (Landscape) bzw. Bild oben, Panel
    // darunter (Portrait) — analog zum Bild-Quiz-Modus (.tq-quiz-layout, siehe
    // style.css). Ohne Bild: Panel füllt die gesamte Fläche und zentriert die
    // Karte (siehe .tq-quiz-standalone in style.css).
    var quizImgs   = _normalizeImages(entry);
    var panelHost  = document.createElement('div');

    if (quizImgs.length) {
        var layout = document.createElement('div');
        layout.className = 'tq-quiz-layout';

        var imagePane = document.createElement('div');
        imagePane.className = 'tq-quiz-image-pane';
        if (quizImgs.length === 2) {
            var dualCont = document.createElement('div');
            dualCont.className = 'tq-dual-image-container';
            dualCont.appendChild(_buildImageEl(imgBase + quizImgs[0].clean));
            dualCont.appendChild(_buildImageEl(imgBase + quizImgs[1].clean));
            imagePane.appendChild(dualCont);
        } else {
            imagePane.appendChild(_buildImageEl(imgBase + quizImgs[0].clean));
        }
        layout.appendChild(imagePane);

        panelHost.className = 'tq-quiz-panel-host';
        layout.appendChild(panelHost);

        textWrapper.appendChild(layout);
    } else {
        panelHost.className = 'tq-quiz-standalone';
        textWrapper.appendChild(panelHost);
    }

    var pairs = [];
    var queue = [];
    var currentIdx = null;

    showStartScreen();

    function showStartScreen() {
        var panel = _tqzPanel();

        var heading = document.createElement('p');
        heading.className   = 'qz-heading';
        heading.textContent = 'In welcher Reihenfolge?';
        panel.appendChild(heading);

        var seqBtn = _qzButton('qz-btn', 'Der Reihe nach');
        seqBtn.addEventListener('click', function () { startQuiz(false); });
        panel.appendChild(seqBtn);

        var randomBtn = _qzButton('qz-btn', 'Zufällig');
        randomBtn.addEventListener('click', function () { startQuiz(true); });
        panel.appendChild(randomBtn);

        panelHost.appendChild(panel);
    }

    function startQuiz(randomOrder) {
        pairs = _tqBuildQuizPairs(quizEntry);
        queue = pairs.map(function (_, i) { return i; });
        if (randomOrder) _qzShuffle(queue);
        nextQuestion();
    }

    function nextQuestion() {
        if (queue.length === 0) {
            showFinishScreen();
            return;
        }
        currentIdx = queue.shift();
        showQuestion();
    }

    function showQuestion() {
        var pair  = pairs[currentIdx];
        var panel = _tqzPanel();

        var label = document.createElement('p');
        label.className   = 'qz-category';
        label.textContent = pair.colName;
        panel.appendChild(label);

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = pair.row.question;
        panel.appendChild(question);

        var answerBtn = _qzButton('qz-btn qz-btn-primary', 'Antwort');
        answerBtn.addEventListener('click', showAnswer);
        panel.appendChild(answerBtn);

        panelHost.appendChild(panel);
    }

    function showAnswer() {
        var pair  = pairs[currentIdx];
        var panel = _tqzPanel();

        var label = document.createElement('p');
        label.className   = 'qz-category';
        label.textContent = pair.colName;
        panel.appendChild(label);

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = pair.row.question;
        panel.appendChild(question);

        var catEl = _buildCategoryBlock(pair.colName, pair.row.answers[pair.colName]);
        if (catEl) {
            var header = catEl.querySelector('.tq-category-header');
            if (header) header.remove(); // Spalten-Label steht bereits oben, keine Dopplung
            panel.appendChild(catEl);
        }

        var hint = document.createElement('p');
        hint.className   = 'qz-hint';
        hint.textContent = 'Meine Antwort war:';
        panel.appendChild(hint);

        var judgeRow = document.createElement('div');
        judgeRow.className = 'qz-judge-row';

        var correctBtn = _qzButton('qz-btn qz-btn-correct', 'Korrekt');
        correctBtn.addEventListener('click', function () { nextQuestion(); });
        judgeRow.appendChild(correctBtn);

        var wrongBtn = _qzButton('qz-btn qz-btn-wrong', 'Falsch');
        wrongBtn.addEventListener('click', function () {
            queue.push(currentIdx);
            nextQuestion();
        });
        judgeRow.appendChild(wrongBtn);

        panel.appendChild(judgeRow);
        panelHost.appendChild(panel);
    }

    function showFinishScreen() {
        var panel = _tqzPanel();

        var heading = document.createElement('p');
        heading.className   = 'qz-heading';
        heading.textContent = 'Quiz abgeschlossen! Alle ' + pairs.length + ' Fragen korrekt beantwortet.';
        panel.appendChild(heading);

        var restartBtn = _qzButton('qz-btn', 'Neu starten');
        restartBtn.addEventListener('click', showStartScreen);
        panel.appendChild(restartBtn);

        panelHost.appendChild(panel);
    }

    function _tqzPanel() {
        panelHost.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';
        return panel;
    }
}

// Sucht den zu entry passenden Eintrag in text-quiz-data.json über die
// Identitätsfelder subject/category/subcategory/view (kein Index-Matching).
function _tqFindQuizEntry(entry, textQuizData) {
    for (var i = 0; i < textQuizData.length; i++) {
        var q = textQuizData[i];
        if (q.subject === entry.subject && q.category === entry.category &&
            q.subcategory === entry.subcategory && q.view === entry.view) {
            return q;
        }
    }
    return null;
}

// Baut die flache Liste aller (Zeile, Spalte)-Paare, die abgefragt werden
// (leere Spaltennamen und Spalten ohne Antworten werden übersprungen).
function _tqBuildQuizPairs(quizEntry) {
    var pairs = [];
    quizEntry.rows.forEach(function (row) {
        quizEntry.columns.forEach(function (colName) {
            if (!colName) return;
            var answers = (row.answers[colName] || []).filter(function (a) { return a; });
            if (!answers.length) return;
            pairs.push({ row: row, colName: colName });
        });
    });
    return pairs;
}
