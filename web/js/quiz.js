var _currentEntry = null;
var _imgBasePath = '';
var _resizeTimer = null;
var _lastLayoutWidth = window.innerWidth;
var _overlayZoom = null;

// ── Image quiz: "Lernen" mode ────────────────────────────────────────────────

function loadLernen(entry, ogImgBasePath) {
    _currentEntry = null;

    var img          = document.getElementById('quiz-img');
    var wrapper      = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder  = document.getElementById('placeholder');
    var textWrapper  = document.getElementById('text-quiz-wrapper');

    img.onload = null;
    zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    img.src = ogImgBasePath + entry.og_filename;
}

// ── Image quiz: "Testen" mode ────────────────────────────────────────────────

function loadQuiz(entry, imgBasePath) {
    _currentEntry = entry;
    _imgBasePath  = imgBasePath;

    var img           = document.getElementById('quiz-img');
    var wrapper       = document.getElementById('quiz-wrapper');
    var zoomContainer = document.getElementById('zoom-container');
    var placeholder   = document.getElementById('placeholder');
    var textWrapper   = document.getElementById('text-quiz-wrapper');

    zoomContainer.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    placeholder.classList.add('hidden');
    textWrapper.classList.add('hidden');
    wrapper.classList.remove('hidden');
    resetZoom();

    img.onload = function () {
        renderOverlays(entry.labels, img, zoomContainer);
    };
    img.src = imgBasePath + entry.filename;
    // If the browser already has this image cached (same URL), onload won't fire.
    if (img.complete && img.naturalWidth > 0) {
        renderOverlays(entry.labels, img, zoomContainer);
    }
}

function renderOverlays(labels, img, wrapper) {
    var scaleX = img.clientWidth  / img.naturalWidth;
    var scaleY = img.clientHeight / img.naturalHeight;

    var existing = wrapper.querySelectorAll('.overlay-group');
    if (existing.length === labels.length) {
        // Resize-Fall: nur Positionen anpassen
        existing.forEach(function (group, i) {
            var lb = labels[i];
            group.style.left = (lb.mask_box.x * scaleX) + 'px';
            group.style.top  = (lb.mask_box.y * scaleY) + 'px';
            var inp = group.querySelector('.label-input');
            if (inp) inp.style.width = (lb.mask_box.w * scaleX) + 'px';
        });
        return;
    }

    wrapper.querySelectorAll('.overlay-group').forEach(function (el) { el.remove(); });

    labels.forEach(function (label) {
        var group = document.createElement('div');
        group.className = 'overlay-group';
        group.style.left = (label.mask_box.x * scaleX) + 'px';
        group.style.top  = (label.mask_box.y * scaleY) + 'px';

        var input = document.createElement('input');
        input.type      = 'text';
        input.className = 'label-input';
        input.style.width    = (label.mask_box.w * scaleX) + 'px';
        input.dataset.solution = label.text;
        input.dataset.ox       = label.anchor_x;
        input.dataset.oy       = label.anchor_y;

        var helpBtn = document.createElement('button');
        helpBtn.type      = 'button';
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
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    if (entry.image) {
        var img = document.createElement('img');
        img.className = 'tq-quiz-image';
        img.alt = '';
        img.src = ogImgBase + entry.image.og;
        img.onerror = function () { img.style.display = 'none'; };
        img.addEventListener('click', function () { _openImageOverlay(img.src); });
        textWrapper.appendChild(img);
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
            categoriesEl.appendChild(catEl);
        });

        section.appendChild(categoriesEl);
        textWrapper.appendChild(section);
    });
}

function loadTextQuiz(entry, imgBase) {
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    if (entry.image) {
        var img = document.createElement('img');
        img.className = 'tq-quiz-image';
        img.alt = '';
        img.src = imgBase + entry.image.clean;
        img.onerror = function () { img.style.display = 'none'; };
        img.addEventListener('click', function () { _openImageOverlay(img.src); });
        textWrapper.appendChild(img);
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
        if (!_currentEntry) return; // null for text quiz and lernen mode

        var img           = document.getElementById('quiz-img');
        var zoomContainer = document.getElementById('zoom-container');

        var savedState = {};
        zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
            savedState[inp.dataset.ox + ',' + inp.dataset.oy] = {
                value:     inp.value,
                className: inp.className,
                bgStyle:   inp.style.background,
                readOnly:  inp.readOnly
            };
        });

        renderOverlays(_currentEntry.labels, img, zoomContainer);

        zoomContainer.querySelectorAll('.label-input').forEach(function (inp) {
            var key = inp.dataset.ox + ',' + inp.dataset.oy;
            if (savedState[key]) {
                inp.value          = savedState[key].value;
                inp.className      = savedState[key].className;
                inp.style.background = savedState[key].bgStyle;
                inp.readOnly       = savedState[key].readOnly;
            }
        });
    }, 120);
});

// ── Zoom initialisieren ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initZoom(document.getElementById('zoom-container'));
});
