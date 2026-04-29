/**
 * buildMenu(data, onSelect)
 *   data     – array from data.json
 *   onSelect – function(entry) called when user clicks an Ansicht
 *
 * Filename format: "Kategorie-Unterkategorie-Ansicht-clean.jpg"
 * Parsing: strip "-clean.{ext}", split on "-":
 *   parts[0] = Kategorie, parts[1] = Unterkategorie, parts[2..] = Ansicht
 */
function buildMenu(data, onSelect) {
    var root = document.getElementById('menu-root');
    var loading = document.getElementById('menu-loading');

    // Build tree: { Kategorie: { Unterkategorie: [{ansicht, entry}] } }
    var tree = {};
    data.forEach(function (entry) {
        var stem = entry.filename.replace(/-clean\.(jpg|jpeg|png|tiff?)$/i, '');
        var parts = stem.split('-');
        if (parts.length < 3) return;

        var kat = parts[0];
        var unter = parts[1];
        var ansicht = parts.slice(2).join('-');

        if (!tree[kat]) tree[kat] = {};
        if (!tree[kat][unter]) tree[kat][unter] = [];
        tree[kat][unter].push({ ansicht: ansicht, entry: entry });
    });

    // DOM builder helpers
    function makeBtn(className, text) {
        var btn = document.createElement('button');
        btn.className = className;
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

    Object.keys(tree).sort().forEach(function (kat) {
        var katLi = document.createElement('li');
        katLi.className = 'menu-kat';

        var katBtn = makeBtn('menu-kat-btn', kat);

        var unterList = document.createElement('ul');
        unterList.className = 'menu-unter-list hidden';

        katBtn.addEventListener('click', function () {
            toggleList(unterList, katBtn);
        });

        Object.keys(tree[kat]).sort().forEach(function (unter) {
            var unterLi = document.createElement('li');
            unterLi.className = 'menu-unter';

            var unterBtn = makeBtn('menu-unter-btn', unter);

            var ansichtList = document.createElement('ul');
            ansichtList.className = 'menu-ansicht-list hidden';

            unterBtn.addEventListener('click', function () {
                toggleList(ansichtList, unterBtn);
            });

            tree[kat][unter].forEach(function (item) {
                var ansichtLi = document.createElement('li');
                var ansichtBtn = makeBtn('menu-ansicht-btn', item.ansicht);

                ansichtBtn.addEventListener('click', function () {
                    document.querySelectorAll('.menu-ansicht-btn.active').forEach(function (b) {
                        b.classList.remove('active');
                    });
                    ansichtBtn.classList.add('active');
                    onSelect(item.entry);
                });

                ansichtLi.appendChild(ansichtBtn);
                ansichtList.appendChild(ansichtLi);
            });

            unterLi.appendChild(unterBtn);
            unterLi.appendChild(ansichtList);
            unterList.appendChild(unterLi);
        });

        katLi.appendChild(katBtn);
        katLi.appendChild(unterList);
        root.appendChild(katLi);
    });

    loading.classList.add('hidden');
    root.classList.remove('hidden');
}
