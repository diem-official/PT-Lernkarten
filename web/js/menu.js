/**
 * buildMenu(data, onSelect)
 *   data     – combined array from data.json + text-data.json
 *   onSelect – function(entry, mode) called when user clicks an Ansicht
 *
 * All entries must have: subject, category, subcategory, view fields.
 */
function buildMenu(data, onSelect) {
    var root    = document.getElementById('menu-root');
    var loading = document.getElementById('menu-loading');

    // Build tree: { Fach: { Kategorie: { Unterkategorie: [{ansicht, entry}] } } }
    var tree = {};
    data.forEach(function (entry) {
        var fach    = entry.subject;
        var kat     = entry.category;
        var unter   = entry.subcategory;
        var ansicht = entry.view;

        if (!fach || !kat || !unter || !ansicht) return;

        if (!tree[fach])             tree[fach]             = {};
        if (!tree[fach][kat])        tree[fach][kat]        = {};
        if (!tree[fach][kat][unter]) tree[fach][kat][unter] = [];
        tree[fach][kat][unter].push({ ansicht: ansicht, entry: entry });
    });

    // DOM builder helpers
    function makeBtn(className, text) {
        var btn = document.createElement('button');
        btn.className   = className;
        btn.textContent = text;
        return btn;
    }

    function toggleList(list, btn) {
        var hidden = list.classList.toggle('hidden');
        if (hidden) {
            btn.classList.remove('expanded');
        } else {
            btn.classList.add('expanded');
        }
    }

    Object.keys(tree).sort().forEach(function (fach) {
        var fachLi  = document.createElement('li');
        fachLi.className = 'menu-fach';

        var fachBtn = makeBtn('menu-fach-btn', fach);

        var katList = document.createElement('ul');
        katList.className = 'menu-fach-list hidden';

        fachBtn.addEventListener('click', function () {
            toggleList(katList, fachBtn);
        });

        Object.keys(tree[fach]).sort().forEach(function (kat) {
            var katLi  = document.createElement('li');
            katLi.className = 'menu-kat';

            var katBtn = makeBtn('menu-kat-btn', kat);

            var unterList = document.createElement('ul');
            unterList.className = 'menu-unter-list hidden';

            katBtn.addEventListener('click', function () {
                toggleList(unterList, katBtn);
            });

            Object.keys(tree[fach][kat]).sort().forEach(function (unter) {
                var unterLi = document.createElement('li');
                unterLi.className = 'menu-unter';

                var unterBtn = makeBtn('menu-unter-btn', unter);

                var ansichtList = document.createElement('ul');
                ansichtList.className = 'menu-ansicht-list hidden';

                unterBtn.addEventListener('click', function () {
                    toggleList(ansichtList, unterBtn);
                });

                tree[fach][kat][unter].forEach(function (item) {
                    var ansichtLi = document.createElement('li');
                    ansichtLi.className = 'menu-ansicht-li';

                    var label     = item.entry.type === 'text'
                        ? item.ansicht + ' ✒'
                        : item.ansicht;
                    var testenBtn = makeBtn('menu-ansicht-btn', label);

                    function setActive() {
                        document.querySelectorAll('.menu-ansicht-li.active').forEach(function (li) {
                            li.classList.remove('active');
                        });
                        ansichtLi.classList.add('active');
                    }

                    testenBtn.addEventListener('click', function () {
                        setActive();
                        onSelect(item.entry, 'testen');
                    });

                    ansichtLi.appendChild(testenBtn);

                    var lernenBtn = makeBtn('menu-lernen-btn', 'Lernen');
                    lernenBtn.addEventListener('click', function () {
                        setActive();
                        onSelect(item.entry, 'lernen');
                    });
                    ansichtLi.appendChild(lernenBtn);

                    ansichtList.appendChild(ansichtLi);
                });

                unterLi.appendChild(unterBtn);
                unterLi.appendChild(ansichtList);
                unterList.appendChild(unterLi);
            });

            katLi.appendChild(katBtn);
            katLi.appendChild(unterList);
            katList.appendChild(katLi);
        });

        fachLi.appendChild(fachBtn);
        fachLi.appendChild(katList);
        root.appendChild(fachLi);
    });

    loading.classList.add('hidden');
    root.classList.remove('hidden');
}
