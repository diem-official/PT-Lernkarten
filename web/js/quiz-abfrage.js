// ── Image quiz: "Quiz" mode ──────────────────────────────────────────────────
// Sequenzielle Einzelabfrage der nummerierten Strukturen mit Selbsteinschätzung
// (Korrekt/Falsch). Falsch beantwortete Nummern werden ans Ende der
// Warteschlange gehängt und später erneut gestellt.

function loadQuizAbfrage(entry, imgBasePath) {
    var img           = document.getElementById('quiz-img');
    var wrapper       = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder   = document.getElementById('placeholder');
    var textWrapper   = document.getElementById('text-quiz-wrapper');
    var answerPanel   = document.getElementById('answer-panel');

    var queue = [];
    var currentIndex = null; // von der Resize-Closure gelesen (siehe _activeMarkerRefresh)

    zoomContainer.querySelectorAll('.marker-badge').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    _activeMarkerRefresh = function () {
        renderMarkers(entry.labels, img, zoomContainer, currentIndex);
    };

    img.onload = _activeMarkerRefresh;
    img.src = imgBasePath + entry.filename;
    // Falls der Browser das Bild schon im Cache hat (gleiche URL), feuert onload nicht.
    if (img.complete && img.naturalWidth > 0) {
        _activeMarkerRefresh();
    }

    showStartScreen();

    function showStartScreen() {
        currentIndex = null;
        _activeMarkerRefresh();

        var panel = _qzPanel();

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

        answerPanel.appendChild(panel);
    }

    function startQuiz(randomOrder) {
        queue = entry.labels.map(function (_, i) { return i; });
        if (randomOrder) _qzShuffle(queue);
        nextQuestion();
    }

    function nextQuestion() {
        if (queue.length === 0) {
            showFinishScreen();
            return;
        }
        currentIndex = queue.shift();
        showQuestion();
    }

    function showQuestion() {
        _activeMarkerRefresh();

        var panel = _qzPanel();

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = 'Wie heißt die Struktur mit der Nummer ' + (currentIndex + 1) + '?';
        panel.appendChild(question);

        var answerBtn = _qzButton('qz-btn qz-btn-primary', 'Antwort');
        answerBtn.addEventListener('click', showAnswer);
        panel.appendChild(answerBtn);

        answerPanel.appendChild(panel);
    }

    function showAnswer() {
        var panel = _qzPanel();

        var question = document.createElement('p');
        question.className   = 'qz-question';
        question.textContent = 'Wie heißt die Struktur mit der Nummer ' + (currentIndex + 1) + '?';
        panel.appendChild(question);

        var solution = document.createElement('p');
        solution.className   = 'qz-solution';
        solution.textContent = entry.labels[currentIndex].text;
        panel.appendChild(solution);

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
            queue.push(currentIndex);
            nextQuestion();
        });
        judgeRow.appendChild(wrongBtn);

        panel.appendChild(judgeRow);
        answerPanel.appendChild(panel);
    }

    function showFinishScreen() {
        currentIndex = null;
        _activeMarkerRefresh();

        var panel = _qzPanel();

        var heading = document.createElement('p');
        heading.className   = 'qz-heading';
        heading.textContent = 'Quiz abgeschlossen! Alle ' + entry.labels.length + ' Strukturen korrekt benannt.';
        panel.appendChild(heading);

        var restartBtn = _qzButton('qz-btn', 'Neu starten');
        restartBtn.addEventListener('click', showStartScreen);
        panel.appendChild(restartBtn);

        answerPanel.appendChild(panel);
    }

    function _qzPanel() {
        answerPanel.innerHTML = '';
        var panel = document.createElement('div');
        panel.className = 'qz-panel';
        return panel;
    }
}

function _qzButton(className, text) {
    var btn = document.createElement('button');
    btn.type      = 'button';
    btn.className = className;
    btn.textContent = text;
    return btn;
}

// Fisher-Yates
function _qzShuffle(array) {
    for (var i = array.length - 1; i > 0; i--) {
        var j   = Math.floor(Math.random() * (i + 1));
        var tmp = array[i];
        array[i] = array[j];
        array[j] = tmp;
    }
    return array;
}
