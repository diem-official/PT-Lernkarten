var _imgBasePath = '';
var _resizeTimer = null;
var _lastLayoutWidth = window.innerWidth;
var _overlayZoom = null;
var _activeMarkerRefresh = null; // Funktion ohne Argumente, oder null (für den Resize-Listener)
var _markerCounterScaleEnabled = false; // true nur im Abfrage-Quiz-Modus (quiz-abfrage.js)

// ── Image quiz: "Lernen" mode ────────────────────────────────────────────────

function loadLernen(entry, ogImgBasePath) {
    _activeMarkerRefresh = null;
    _markerCounterScaleEnabled = false;

    var img          = document.getElementById('quiz-img');
    var wrapper      = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder  = document.getElementById('placeholder');
    var textWrapper  = document.getElementById('text-quiz-wrapper');
    var answerPanel  = document.getElementById('answer-panel');

    img.onload = null;
    zoomContainer.querySelectorAll('.marker-badge').forEach(function (el) { el.remove(); });
    answerPanel.innerHTML = '';

    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    img.src = ogImgBasePath + entry.og_filename;
}

// ── Image quiz: "Schreiben" mode ─────────────────────────────────────────────

function loadQuiz(entry, imgBasePath) {
    _imgBasePath  = imgBasePath;
    _markerCounterScaleEnabled = false;

    var img           = document.getElementById('quiz-img');
    var wrapper       = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder   = document.getElementById('placeholder');
    var textWrapper   = document.getElementById('text-quiz-wrapper');
    var answerPanel   = document.getElementById('answer-panel');

    zoomContainer.querySelectorAll('.marker-badge').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    renderAnswerPanel(entry.labels, answerPanel);

    _activeMarkerRefresh = function () {
        renderMarkers(entry.labels, img, zoomContainer);
    };

    img.onload = _activeMarkerRefresh;
    img.src = imgBasePath + entry.filename;
    // If the browser already has this image cached (same URL), onload won't fire.
    if (img.complete && img.naturalWidth > 0) {
        _activeMarkerRefresh();
    }
}

// Numbered dots on the image, positioned where the label used to be.
// highlightIndex (optional): 0-basierter Index des Labels, dessen Marker
// hervorgehoben werden soll (Abfrage-Quiz-Modus).
function renderMarkers(labels, img, zoomContainer, highlightIndex) {
    var scaleX = img.clientWidth  / img.naturalWidth;
    var scaleY = img.clientHeight / img.naturalHeight;

    zoomContainer.querySelectorAll('.marker-badge').forEach(function (el) { el.remove(); });

    labels.forEach(function (label, i) {
        var badge = document.createElement('div');
        badge.className   = 'marker-badge number-badge';
        if (i === highlightIndex) badge.classList.add('marker-badge--active');
        badge.textContent = i + 1;
        badge.style.left  = ((label.mask_box.x + label.mask_box.w / 2) * scaleX) + 'px';
        badge.style.top   = ((label.mask_box.y + label.mask_box.h / 2) * scaleY) + 'px';
        zoomContainer.appendChild(badge);
    });

    if (_markerCounterScaleEnabled) {
        applyMarkerCounterScale(zoomContainer, window.getZoomScale());
    }
}

// Hält die Bildschirmgröße der Marker beim Zoomen konstant (statt mit dem
// Bild mitzuwachsen), damit sich eng beieinanderliegende Marker beim
// Hineinzoomen entzerren statt überlappt zu bleiben.
function applyMarkerCounterScale(zoomContainer, s) {
    zoomContainer.querySelectorAll('.marker-badge').forEach(function (badge) {
        badge.style.transform = 'translate(-50%, -50%) scale(' + (1 / s) + ')';
    });
}

// Numbered input rows in the side/bottom panel.
function renderAnswerPanel(labels, panel) {
    panel.innerHTML = '';

    labels.forEach(function (label, i) {
        var row = document.createElement('div');
        row.className = 'answer-row';

        var number = document.createElement('div');
        number.className   = 'answer-number number-badge';
        number.textContent = i + 1;

        var input = document.createElement('input');
        input.type      = 'text';
        input.className = 'label-input';
        input.dataset.solution = label.text;

        var helpBtn = document.createElement('button');
        helpBtn.type      = 'button';
        helpBtn.className = 'help-btn';
        helpBtn.textContent = '?';
        helpBtn.setAttribute('aria-label', 'Lösung anzeigen');

        (function (inp, solution) {
            inp.addEventListener('input', function () { onInputChange(inp); });
            helpBtn.addEventListener('click', function () { showHelp(solution); });
        }(input, label.text));

        row.appendChild(number);
        row.appendChild(input);
        row.appendChild(helpBtn);
        panel.appendChild(row);
    });
}

function onInputChange(input) {
    if (input.readOnly) return;

    var value    = input.value;
    var solution = input.dataset.solution;

    if (value.length === 0) {
        input.className    = 'label-input';
        input.style.background = '';
        return;
    }

    var isPrefix = solution.toLowerCase().startsWith(value.toLowerCase());

    if (!isPrefix) {
        input.className    = 'label-input typo';
        input.style.background = '';
    } else if (value.length === solution.length) {
        input.style.background = '';
        input.className    = 'label-input correct';
        input.readOnly     = true;
    } else {
        var alpha = (value.length / solution.length).toFixed(2);
        input.style.background = 'rgba(80, 200, 100, ' + alpha + ')';
        input.className    = 'label-input';
    }
}

// ── Text quiz ────────────────────────────────────────────────────────────────

function _normalizeImages(entry) {
    if (entry.images && entry.images.length) return entry.images;
    if (entry.image) return [entry.image];
    return [];
}

function _buildImageEl(src) {
    var img = document.createElement('img');
    img.className = 'tq-quiz-image';
    img.alt = '';
    img.src = src;
    img.onerror = function () { img.style.display = 'none'; };
    img.addEventListener('click', function () { _openImageOverlay(img.src); });
    return img;
}

function _textWrapperSetup() {
    var placeholder = document.getElementById('placeholder');
    var quizWrapper = document.getElementById('quiz-wrapper');
    var textWrapper = document.getElementById('text-quiz-wrapper');
    placeholder.classList.add('hidden');
    quizWrapper.classList.add('hidden');
    textWrapper.classList.remove('hidden');
    textWrapper.innerHTML = '';
    return textWrapper;
}

function _parseAnswer(answerFull) {
    var colonIdx = answerFull.indexOf(':');
    if (colonIdx === -1) return { prefix: null, solution: answerFull };
    return {
        prefix:   answerFull.slice(0, colonIdx).trim(),
        solution: answerFull.slice(colonIdx + 1).trim()
    };
}

function _openImageOverlay(src) {
    var overlay = document.getElementById('tq-image-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'tq-image-overlay';
        overlay.className = 'tq-image-overlay';

        var zoomCont = document.createElement('div');
        zoomCont.className = 'tq-overlay-zoom-container';

        var img = document.createElement('img');
        img.id = 'tq-image-overlay-img';
        img.className = 'tq-image-overlay-img';
        img.alt = '';
        zoomCont.appendChild(img);
        overlay.appendChild(zoomCont);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'tq-overlay-close';
        closeBtn.textContent = '×';
        closeBtn.setAttribute('aria-label', 'Schließen');
        closeBtn.addEventListener('click', function () {
            overlay.classList.remove('tq-image-overlay--visible');
            _overlayZoom.reset();
        });
        overlay.appendChild(closeBtn);

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                overlay.classList.remove('tq-image-overlay--visible');
                _overlayZoom.reset();
            }
        });

        document.body.appendChild(overlay);
        _overlayZoom = window.createZoom(zoomCont);
    }
    document.getElementById('tq-image-overlay-img').src = src;
    _overlayZoom.reset();
    overlay.classList.add('tq-image-overlay--visible');
}

// Lernen mode: shows all questions and answers as static text
function loadTextLernen(entry, ogImgBase) {
    _activeMarkerRefresh = null;
    var textWrapper = _textWrapperSetup();

    var lernenImgs = _normalizeImages(entry);
    if (lernenImgs.length === 2) {
        var dualCont = document.createElement('div');
        dualCont.className = 'tq-dual-image-container';
        dualCont.appendChild(_buildImageEl(ogImgBase + lernenImgs[0].og));
        dualCont.appendChild(_buildImageEl(ogImgBase + lernenImgs[1].og));
        textWrapper.appendChild(dualCont);
    } else if (lernenImgs.length === 1) {
        textWrapper.appendChild(_buildImageEl(ogImgBase + lernenImgs[0].og));
    }

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';

        var questionEl = document.createElement('div');
        questionEl.className   = 'tq-question';
        questionEl.textContent = row.question;
        section.appendChild(questionEl);

        var categoriesEl = document.createElement('div');
        categoriesEl.className = 'tq-categories';

        entry.columns.forEach(function (colName) {
            var catEl = _buildCategoryBlock(colName, row.answers[colName]);
            if (catEl) categoriesEl.appendChild(catEl);
        });

        section.appendChild(categoriesEl);
        textWrapper.appendChild(section);
    });
}

// Category block: Label-Header + Liste der geparsten Antwort-Fragmente
// (Präfix-Handling über _parseAnswer). Genutzt vom Lernen-Modus (alle Spalten
// einer Zeile) und vom Antwort-Reveal im Text-Quiz-Abfrage-Modus (eine Spalte).
// Gibt null zurück, wenn die Spalte keine Antworten hat.
function _buildCategoryBlock(colName, rawAnswers) {
    var answers = (rawAnswers || []).filter(function (a) { return a; });
    if (!answers.length) return null;

    var catEl = document.createElement('div');
    catEl.className = 'tq-category';

    var headerEl = document.createElement('div');
    headerEl.className = 'tq-category-header';
    var labelEl = document.createElement('span');
    labelEl.className   = 'tq-category-label';
    labelEl.textContent = colName;
    headerEl.appendChild(labelEl);

    var fieldsEl = document.createElement('div');
    fieldsEl.className = 'tq-fields';

    answers.forEach(function (answerFull) {
        var parsed = _parseAnswer(answerFull);
        var answerEl = document.createElement('div');
        answerEl.className = 'tq-answer-text';
        if (parsed.prefix) {
            var prefixSpan = document.createElement('span');
            prefixSpan.className   = 'tq-field-prefix';
            prefixSpan.textContent = parsed.prefix + ':';
            var valueSpan = document.createElement('span');
            valueSpan.textContent = ' ' + parsed.solution;
            answerEl.appendChild(prefixSpan);
            answerEl.appendChild(valueSpan);
        } else {
            answerEl.textContent = parsed.solution;
        }
        fieldsEl.appendChild(answerEl);
    });

    catEl.appendChild(headerEl);
    catEl.appendChild(fieldsEl);
    return catEl;
}

function loadTextQuiz(entry, imgBase) {
    _activeMarkerRefresh = null;
    var textWrapper = _textWrapperSetup();

    var quizImgs = _normalizeImages(entry);
    if (quizImgs.length === 2) {
        var dualCont = document.createElement('div');
        dualCont.className = 'tq-dual-image-container';
        dualCont.appendChild(_buildImageEl(imgBase + quizImgs[0].clean));
        dualCont.appendChild(_buildImageEl(imgBase + quizImgs[1].clean));
        textWrapper.appendChild(dualCont);
    } else if (quizImgs.length === 1) {
        textWrapper.appendChild(_buildImageEl(imgBase + quizImgs[0].clean));
    }

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';

        var questionEl = document.createElement('div');
        questionEl.className   = 'tq-question';
        questionEl.textContent = row.question;
        section.appendChild(questionEl);

        var categoriesEl = document.createElement('div');
        categoriesEl.className = 'tq-categories';

        entry.columns.forEach(function (colName) {
            var answers = (row.answers[colName] || []).filter(function (a) { return a; });
            if (!answers.length) return;

            var prefixGroups = {};
            answers.forEach(function(answerFull) {
                var parsed = _parseAnswer(answerFull);
                if (parsed.prefix) {
                    if (!prefixGroups[parsed.prefix]) prefixGroups[parsed.prefix] = [];
                    prefixGroups[parsed.prefix].push(parsed.solution);
                }
            });

            var categoryState = { answers: answers, claimed: new Map(), prefixPools: {} };
            Object.keys(prefixGroups).forEach(function(prefix) {
                if (prefixGroups[prefix].length > 1) {
                    categoryState.prefixPools[prefix] = {
                        answers: prefixGroups[prefix],
                        claimed: new Map()
                    };
                }
            });

            var catEl = document.createElement('div');
            catEl.className = 'tq-category';

            var headerEl = document.createElement('div');
            headerEl.className = 'tq-category-header';

            var labelEl = document.createElement('span');
            labelEl.className   = 'tq-category-label';
            labelEl.textContent = colName;

            var helpBtn = document.createElement('button');
            helpBtn.type      = 'button';
            helpBtn.className = 'help-btn';
            helpBtn.textContent = '?';
            helpBtn.setAttribute('aria-label', 'Hinweis anzeigen');

            (function (state) {
                helpBtn.addEventListener('click', function () {
                    onTextHelpClick(state);
                });
            }(categoryState));

            headerEl.appendChild(labelEl);
            headerEl.appendChild(helpBtn);

            var fieldsEl = document.createElement('div');
            fieldsEl.className = 'tq-fields';

            answers.forEach(function (answerFull, fieldIdx) {
                var parsed = _parseAnswer(answerFull);

                var input = document.createElement('input');
                input.type = 'text';
                input.className = 'label-input tq-input';
                input.setAttribute('autocomplete', 'off');
                input.setAttribute('autocorrect', 'off');
                input.setAttribute('autocapitalize', 'off');
                input.setAttribute('spellcheck', 'false');

                if (parsed.prefix) {
                    if (categoryState.prefixPools[parsed.prefix]) {
                        input.dataset.poolPrefix = parsed.prefix;
                    } else {
                        input.dataset.fixedAnswer = parsed.solution;
                        input.dataset.fullAnswer  = answerFull;
                    }
                }

                (function (inp, idx, state) {
                    inp.addEventListener('input', function () {
                        onTextInputChange(inp, idx, state);
                    });
                }(input, fieldIdx, categoryState));

                if (parsed.prefix) {
                    var fieldRow = document.createElement('div');
                    fieldRow.className = 'tq-field-row';
                    var prefixSpan = document.createElement('span');
                    prefixSpan.className   = 'tq-field-prefix';
                    prefixSpan.textContent = parsed.prefix + ':';
                    fieldRow.appendChild(prefixSpan);
                    fieldRow.appendChild(input);
                    fieldsEl.appendChild(fieldRow);
                } else {
                    fieldsEl.appendChild(input);
                }
            });

            catEl.appendChild(headerEl);
            catEl.appendChild(fieldsEl);
            categoriesEl.appendChild(catEl);
        });

        section.appendChild(categoriesEl);
        textWrapper.appendChild(section);
    });
}

// Returns the answers not yet claimed by other fields (not the current field).
function _textPool(categoryState, currentFieldIdx) {
    var otherClaims = [];
    categoryState.claimed.forEach(function (answer, fieldIdx) {
        if (fieldIdx !== currentFieldIdx) otherClaims.push(answer);
    });
    return categoryState.answers.filter(function (a) {
        return otherClaims.indexOf(a) === -1;
    });
}

function _prefixPool(prefixState, currentFieldIdx) {
    var otherClaims = [];
    prefixState.claimed.forEach(function(answer, fieldIdx) {
        if (fieldIdx !== currentFieldIdx) otherClaims.push(answer);
    });
    return prefixState.answers.filter(function(a) {
        return otherClaims.indexOf(a) === -1;
    });
}

function onTextInputChange(input, fieldIdx, categoryState) {
    if (input.readOnly) return;

    var value = input.value;

    if (value.length === 0) {
        input.className        = 'label-input tq-input';
        input.style.background = '';
        return;
    }

    // Pool-Validierung für Präfix-Felder mit mehreren Antworten
    if (input.dataset.poolPrefix) {
        var prefixState  = categoryState.prefixPools[input.dataset.poolPrefix];
        var valueLower   = value.toLowerCase();
        var pool         = _prefixPool(prefixState, fieldIdx);

        var bestMatch    = null;
        var bestProgress = 0;

        pool.forEach(function(answer) {
            if (answer.toLowerCase().startsWith(valueLower)) {
                var progress = value.length / answer.length;
                if (progress > bestProgress) {
                    bestProgress = progress;
                    bestMatch    = answer;
                }
            }
        });

        if (bestMatch) {
            if (value.length === bestMatch.length) {
                input.style.background = '';
                input.className        = 'label-input tq-input correct';
                input.readOnly         = true;
                prefixState.claimed.set(fieldIdx, bestMatch);
                categoryState.claimed.set(fieldIdx, input.dataset.poolPrefix + ': ' + bestMatch);
            } else {
                input.style.background = 'rgba(80, 200, 100, ' + bestProgress.toFixed(2) + ')';
                input.className        = 'label-input tq-input';
            }
            return;
        }

        input.className        = 'label-input tq-input typo';
        input.style.background = '';
        return;
    }

    // Fixed-answer field (colon-prefixed): validate only against its specific solution
    if (input.dataset.fixedAnswer) {
        var solution   = input.dataset.fixedAnswer;
        var isPrefix   = solution.toLowerCase().startsWith(value.toLowerCase());
        if (!isPrefix) {
            input.className        = 'label-input tq-input typo';
            input.style.background = '';
        } else if (value.length === solution.length) {
            input.style.background = '';
            input.className        = 'label-input tq-input correct';
            input.readOnly         = true;
            categoryState.claimed.set(fieldIdx, input.dataset.fullAnswer);
        } else {
            var alpha = (value.length / solution.length).toFixed(2);
            input.style.background = 'rgba(80, 200, 100, ' + alpha + ')';
            input.className        = 'label-input tq-input';
        }
        return;
    }

    var valueLower = value.toLowerCase();
    var pool       = _textPool(categoryState, fieldIdx);

    var bestMatch    = null;
    var bestProgress = 0;

    pool.forEach(function (answer) {
        if (answer.toLowerCase().startsWith(valueLower)) {
            var progress = value.length / answer.length;
            if (progress > bestProgress) {
                bestProgress = progress;
                bestMatch    = answer;
            }
        }
    });

    if (bestMatch) {
        if (value.length === bestMatch.length) {
            input.style.background = '';
            input.className        = 'label-input tq-input correct';
            input.readOnly         = true;
            categoryState.claimed.set(fieldIdx, bestMatch);
        } else {
            input.style.background = 'rgba(80, 200, 100, ' + bestProgress.toFixed(2) + ')';
            input.className        = 'label-input tq-input';
        }
        return;
    }

    input.className        = 'label-input tq-input typo';
    input.style.background = '';
}

function onTextHelpClick(categoryState) {
    var allClaimed = [];
    categoryState.claimed.forEach(function (answer) { allClaimed.push(answer); });
    var remaining = categoryState.answers.filter(function (a) {
        return allClaimed.indexOf(a) === -1;
    });
    if (remaining.length === 0) {
        showHelp('Alle Antworten korrekt ✓');
    } else {
        var hint = remaining[Math.floor(Math.random() * remaining.length)];
        showHelp(hint);
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

window.showHelp = showHelp;

// ── Resize handler (debounced) — image quiz only ─────────────────────────────

window.addEventListener('resize', function () {
    var newWidth = window.innerWidth;
    var onlyHeightChanged = (newWidth === _lastLayoutWidth);
    _lastLayoutWidth = newWidth;

    if (onlyHeightChanged) return;

    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(function () {
        if (!_activeMarkerRefresh) return; // null for text quiz and lernen mode

        _activeMarkerRefresh();
    }, 120);
});

// ── Zoom initialisieren ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'), {
        onTransform: function (state) {
            if (_markerCounterScaleEnabled) {
                applyMarkerCounterScale(document.getElementById('zoom-container'), state.s);
            }
        }
    });
});
