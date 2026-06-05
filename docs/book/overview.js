// Overview page: a visual grid of all interviews, grouped. Clicking a card
// opens the per-interview explorer (interview.html#<datasetId>).
(function () {
    "use strict";

    const FALLBACK_ICON = "icons/system-design.png";

    const els = {
        overview: document.getElementById("overview"),
        results: document.getElementById("overview-results"),
        status: document.getElementById("overview-status"),
        search: document.getElementById("overview-search"),
        searchInput: document.getElementById("overview-search-input"),
        searchEmpty: document.getElementById("overview-search-empty"),
        error: document.getElementById("error-banner"),
    };

    // All groups as loaded; the current search filters a copy of this.
    let allGroups = [];

    function showError(msg) {
        if (els.error) {
            els.error.textContent = msg;
            els.error.hidden = false;
        }
    }

    async function fetchJson(path) {
        const res = await fetch(path, {cache: "no-cache"});
        if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
        return res.json();
    }

    function normalizeGroups(manifest) {
        const groups = manifest && Array.isArray(manifest.groups) ? manifest.groups : [];
        return groups
            .filter((g) => g && Array.isArray(g.datasets))
            .map((g) => ({
                id: g.id || g.name || "group",
                name: g.name || g.id || "Group",
                datasets: g.datasets,
            }));
    }

    // data/<id>/interview.json -> data/<id>/icon.png
    function iconPathFor(dataset) {
        if (dataset.icon) return dataset.icon;
        const dir = String(dataset.path || "").replace(/\/[^/]*$/, "");
        return dir ? `${dir}/icon.png` : FALLBACK_ICON;
    }

    function makeCard(dataset) {
        const card = document.createElement("a");
        card.className = "interview-card";
        card.href = `interview.html#${dataset.id}`;

        const img = document.createElement("img");
        img.className = "interview-icon";
        img.loading = "lazy";
        img.alt = "";
        img.src = iconPathFor(dataset);
        // Fall back to the shared icon if the per-interview one is missing.
        img.addEventListener("error", function onErr() {
            if (img.src.endsWith(FALLBACK_ICON)) return; // already fell back
            img.removeEventListener("error", onErr);
            img.src = FALLBACK_ICON;
        });

        const name = document.createElement("span");
        name.className = "interview-name";
        name.textContent = dataset.name || dataset.id;

        card.appendChild(img);
        card.appendChild(name);
        return card;
    }

    function render(groups) {
        els.results.innerHTML = "";
        // Hide group titles when only one group is *visible* (matches the
        // original single-group layout, and keeps a filtered-to-one-group
        // result from showing a lone heading).
        const single = groups.length <= 1;
        groups.forEach((g) => {
            const section = document.createElement("section");
            section.className = "group-section";

            if (!single) {
                const h = document.createElement("h2");
                h.className = "group-title";
                h.textContent = g.name;
                section.appendChild(h);
            }

            const grid = document.createElement("div");
            grid.className = "overview-grid";
            g.datasets.forEach((d) => grid.appendChild(makeCard(d)));
            section.appendChild(grid);
            els.results.appendChild(section);
        });
    }

    function datasetMatches(dataset, groupName, query) {
        const haystack = [
            dataset.name,
            dataset.id,
            groupName,
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
        return haystack.includes(query);
    }

    // Returns a filtered copy of allGroups: groups keep only matching datasets,
    // and groups with no remaining datasets are dropped. An empty query returns
    // everything unchanged.
    function filterGroups(query) {
        const q = query.trim().toLowerCase();
        if (!q) return allGroups;
        return allGroups
            .map((g) => ({
                ...g,
                datasets: g.datasets.filter((d) => datasetMatches(d, g.name, q)),
            }))
            .filter((g) => g.datasets.length > 0);
    }

    function applySearch() {
        const query = els.searchInput ? els.searchInput.value : "";
        const groups = filterGroups(query);
        render(groups);
        const hasResults = groups.some((g) => g.datasets.length > 0);
        if (els.searchEmpty) els.searchEmpty.hidden = hasResults;
    }

    async function init() {
        try {
            const manifest = await fetchJson("data/index.json");
            const groups = normalizeGroups(manifest);
            const total = groups.reduce((n, g) => n + g.datasets.length, 0);
            if (total === 0) {
                throw new Error('data/index.json must contain a non-empty "groups" array');
            }
            allGroups = groups;
            if (els.status) els.status.hidden = true;
            if (els.search) els.search.hidden = false;
            if (els.searchInput) {
                els.searchInput.addEventListener("input", applySearch);
            }
            applySearch();
        } catch (err) {
            if (els.status) els.status.textContent = "";
            showError(err.message || String(err));
        }
    }

    init();
})();
