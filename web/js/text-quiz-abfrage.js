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

    var pairs       = [];
    var queue       = [];
    var currentIdx  = null;
    var listStatus  = [];

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

        var listBtn = _qzButton('qz-btn', 'Aus Liste');
        listBtn.addEventListener('click', showListScreen);
        panel.appendChild(listBtn);

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
        askCurrent();
    }

    function askCurrent() {
        _tqzRenderQuestionStep(panelHost, pairs[currentIdx], function (verdict) {
            if (verdict === 'wrong') queue.push(currentIdx);
            nextQuestion();
        });
    }

    // ── "Aus Liste": alle Fragen gruppiert nach Zeile, frei wählbare
    // Reihenfolge über ein Pop-up statt linearer Warteschlange ─────────────
    function showListScreen() {
        pairs      = _tqBuildQuizPairs(quizEntry);
        listStatus = pairs.map(function () { return null; }); // null | 'correct' | 'wrong'
        renderList();
    }

    function renderList() {
        var panel = _tqzPanel();
        panel.classList.add('qz-panel--scrollable');

        var heading = document.createElement('p');
        heading.className   = 'qz-heading';
        heading.textContent = 'Wähle eine Frage aus der Liste.';
        panel.appendChild(heading);

        _tqzGroupPairsByRow(pairs).forEach(function (group) {
            var groupEl = document.createElement('div');
            groupEl.className = 'qz-list-group';

            var rowLabel = document.createElement('p');
            rowLabel.className   = 'qz-category';
            rowLabel.textContent = group.row.question;
            groupEl.appendChild(rowLabel);

            var rowEl = document.createElement('div');
            rowEl.className = 'qz-list-row';

            group.items.forEach(function (item) {
                var btn = _qzButton('qz-btn', item.pair.colName);
                _tqzApplyStatus(btn, listStatus[item.index]);
                btn.addEventListener('click', function () {
                    openQuestionModal(item.index);
                });
                rowEl.appendChild(btn);
            });

            groupEl.appendChild(rowEl);
            panel.appendChild(groupEl);
        });

        panelHost.appendChild(panel);
    }

    // Setzt/entfernt die Bewertungs-Darstellung eines Listen-Buttons anhand
    // von status ('correct' | 'wrong' | null). Nutzt die bereits bestehenden
    // Klassen .qz-btn-correct/.qz-btn-wrong — identisch zu den Korrekt/Falsch-
    // Buttons, keine neue Farb-Regel nötig.
    function _tqzApplyStatus(btn, status) {
        btn.classList.remove('qz-btn-correct', 'qz-btn-wrong');
        if (status === 'correct') {
            btn.classList.add('qz-btn-correct');
            btn.textContent = '✓ ' + btn.textContent;
        } else if (status === 'wrong') {
            btn.classList.add('qz-btn-wrong');
            btn.textContent = '✗ ' + btn.textContent;
        }
    }

    function openQuestionModal(pairIndex) {
        var overlay = _tqzEnsureModal();
        var box = document.getElementById('tqz-modal-box');

        _tqzRenderQuestionStep(box, pairs[pairIndex], function (verdict) {
            listStatus[pairIndex] = verdict;
            closeQuestionModal();
            renderList();
            _tqzCheckFinished();
        });

        overlay.classList.add('qz-modal-overlay--visible');
        document.getElementById('tqz-modal-close').focus();
    }

    function closeQuestionModal() {
        document.getElementById('tqz-question-modal').classList.remove('qz-modal-overlay--visible');
    }

    function _tqzCheckFinished() {
        var allCorrect = listStatus.length > 0 && listStatus.every(function (s) {
            return s === 'correct';
        });
        if (allCorrect) showFinishScreen();
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

// Gruppiert die (bereits Zeile×Spalte-sortierten) pairs nach Zeile, für die
// Darstellung im "Aus Liste"-Modus. Kein Objekt-Keying über Zeilennamen
// nötig — ein simpler "gleiche Zeile wie letzte Gruppe?"-Vergleich reicht,
// da pairs aus _tqBuildQuizPairs bereits zeilenweise geordnet ist.
function _tqzGroupPairsByRow(pairs) {
    var groups = [];
    pairs.forEach(function (pair, index) {
        var last = groups[groups.length - 1];
        if (!last || last.row !== pair.row) {
            last = { row: pair.row, items: [] };
            groups.push(last);
        }
        last.items.push({ pair: pair, index: index });
    });
    return groups;
}

// Rendert die Frage-Karte für `pair` in `container` (container wird geleert).
// Nach Bewertung (Korrekt/Falsch-Klick) wird onJudged('correct'|'wrong')
// aufgerufen — der Aufrufer entscheidet, was danach passiert (nächste Frage,
// Modal schließen, ...). Gemeinsam genutzt von askCurrent (Sequenziell/
// Zufällig, rendert in panelHost) und openQuestionModal (Aus Liste, rendert
// in die Modal-Box).
function _tqzRenderQuestionStep(container, pair, onJudged) {
    renderQuestion();

    function renderQuestion() {
        container.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';

        var label = document.createElement('p');
        label.className   = 'qz-category';
        label.textContent = pair.colName;
        panel.appendChild(label);

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = pair.row.question;
        panel.appendChild(question);

        var answerBtn = _qzButton('qz-btn qz-btn-primary', 'Antwort');
        answerBtn.addEventListener('click', renderAnswer);
        panel.appendChild(answerBtn);

        container.appendChild(panel);
    }

    function renderAnswer() {
        container.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';

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
        correctBtn.addEventListener('click', function () { onJudged('correct'); });
        judgeRow.appendChild(correctBtn);

        var wrongBtn = _qzButton('qz-btn qz-btn-wrong', 'Falsch');
        wrongBtn.addEventListener('click', function () { onJudged('wrong'); });
        judgeRow.appendChild(wrongBtn);

        panel.appendChild(judgeRow);
        container.appendChild(panel);
    }
}

// Einmalig lazy angelegtes Overlay-Element für das "Aus Liste"-Pop-up.
// Modul-Ebene (wie _qzButton/_qzShuffle), idempotent über getElementById —
// KEINE Cache-Variable, da loadTextQuizAbfrage bei jedem Ansichtswechsel neu
// ausgeführt wird und eine dort gehaltene Variable jedes Mal zurückgesetzt
// würde (siehe _activeMarkerRefresh = null; oben), was ein doppeltes,
// verwaistes Overlay-Element erzeugen würde. Analog zu _openImageOverlay in
// quiz.js.
function _tqzEnsureModal() {
    var overlay = document.getElementById('tqz-question-modal');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'tqz-question-modal';
    overlay.className = 'qz-modal-overlay';

    var box = document.createElement('div');
    box.id = 'tqz-modal-box';
    box.className = 'qz-modal-box';
    overlay.appendChild(box);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.id = 'tqz-modal-close';
    closeBtn.className = 'tq-overlay-close';
    closeBtn.textContent = '×';
    closeBtn.setAttribute('aria-label', 'Schließen');
    closeBtn.addEventListener('click', function () {
        overlay.classList.remove('qz-modal-overlay--visible');
    });
    overlay.appendChild(closeBtn);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') overlay.classList.remove('qz-modal-overlay--visible');
    });

    document.body.appendChild(overlay);
    return overlay;
}
