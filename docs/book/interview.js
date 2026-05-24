// System Design Step-by-Step Explorer
// Vanilla JS, no build step. Loads a manifest of datasets, then a per-dataset
// JSON file containing both dataset-level interview sections (requirements,
// capacity, API, data model, follow-ups) and a sequence of architecture
// steps with Mermaid diagrams.

(function () {
    "use strict";

    // ---------- Mermaid setup ----------
    mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "strict",
        "padding": 5,
        flowchart: {htmlLabels: true, curve: "basis", useMaxWidth: true},
    });

    // ---------- DOM ----------
    const els = {
        datasetTitle: document.getElementById("dataset-title"),
        datasetDescription: document.getElementById("dataset-description"),
        datasetSelect: document.getElementById("dataset-select"),
        navList: document.getElementById("nav-list"),
        stepTitle: document.getElementById("step-title"),
        stepDescription: document.getElementById("step-description"),
        stepCounter: document.getElementById("step-counter"),
        prevBtn: document.getElementById("prev-btn"),
        nextBtn: document.getElementById("next-btn"),
        diagramBlock: document.getElementById("diagram-block"),
        diagramViewTabs: document.getElementById("diagram-view-tabs"),
        diagram: document.getElementById("diagram"),
        optionTabs: document.getElementById("option-tabs"),
        optionProsCons: document.getElementById("option-proscons"),
        introBlock: document.getElementById("intro-block"),
        stepExtras: document.getElementById("step-extras"),
        errorBanner: document.getElementById("error-banner"),
    };

    // ---------- State ----------
    const state = {
        datasets: [],           // flat list, each with groupId/groupName
        groups: [],             // [{ id, name, datasets }, ...]
        currentDatasetId: null,
        data: null,
        entries: [],            // [{ kind, id, title, payload? }, ...]
        currentEntryIndex: 0,
        currentOptionIndex: 0,  // per-step (reset on entry change)
        currentFlowIndex: 0,    // per-step (reset on entry change)
        currentDiagramView: "focus",
    };

    // Slugs used by intro entries when building/parsing #hash links.
    const INTRO_SLUGS = {
        requirements: "requirements",
        capacity: "capacity",
        api: "api",
        dataModel: "data-model",
        patterns: "patterns",
        patternCatalog: "pattern-catalog",
        finalDesign: "final-design",
        apiFlows: "api-flows",
        satisfies: "satisfies",
        interviewScript: "interview-script",
        levelVariants: "by-level",
        followUps: "follow-ups",
    };

    // Slugs that belong in the bottom "Wrap-up" sidebar group, in order.
    const WRAPUP_ORDER = [
        INTRO_SLUGS.finalDesign,
        INTRO_SLUGS.apiFlows,
        INTRO_SLUGS.satisfies,
        INTRO_SLUGS.interviewScript,
        INTRO_SLUGS.levelVariants,
        INTRO_SLUGS.followUps,
    ];
    const WRAPUP_SLUGS = new Set(WRAPUP_ORDER);

    // ---------- Utilities ----------

    function showError(msg) {
        els.errorBanner.hidden = false;
        els.errorBanner.textContent = msg;
    }

    function clearError() {
        els.errorBanner.hidden = true;
        els.errorBanner.textContent = "";
    }

    async function fetchJson(path) {
        const res = await fetch(path, {cache: "no-cache"});
        if (!res.ok) throw new Error(`Failed to fetch ${path}: HTTP ${res.status}`);
        try {
            return await res.json();
        } catch (e) {
            throw new Error(`Invalid JSON in ${path}: ${e.message}`);
        }
    }

    function diagramSource(value) {
        if (Array.isArray(value)) return value.join("\n");
        return typeof value === "string" ? value : "";
    }

    function hasDiagram(value) {
        return diagramSource(value).trim() !== "";
    }

    function pickDiagram() {
        for (const value of arguments) {
            if (hasDiagram(value)) return diagramSource(value);
        }
        return "";
    }

    function hasStepLikeDiagram(item) {
        if (!item || typeof item !== "object") return false;
        const hasOwn = hasDiagram(item.diagram);
        const hasOpt = Array.isArray(item.options) && item.options.length > 0 &&
            item.options.every((o) => o && hasDiagram(o.diagram));
        return hasOwn || hasOpt;
    }

    // Extract Mermaid node IDs from a diagram source.
    function extractNodeIds(diagram) {
        diagram = diagramSource(diagram);
        if (!diagram) return new Set();
        const ids = new Set();
        const reLabeled = /(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)/g;
        let m;
        while ((m = reLabeled.exec(diagram)) !== null) ids.add(m[1]);
        const reEdge = /([A-Za-z_][A-Za-z0-9_-]*)\s*(?:--+>|--+|==+>|-\.-+>|<-+>|<--+)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)/g;
        while ((m = reEdge.exec(diagram)) !== null) {
            ids.add(m[1]);
            ids.add(m[2]);
        }
        const reserved = new Set([
            "graph", "flowchart", "subgraph", "end", "classDef", "class",
            "LR", "RL", "TB", "BT", "TD",
        ]);
        for (const r of reserved) ids.delete(r);
        return ids;
    }

    function computeAutoDiff(cur, prev) {
        const a = extractNodeIds(cur);
        const b = extractNodeIds(prev);
        const out = [];
        for (const id of a) if (!b.has(id)) out.push(id);
        return out;
    }

    function resolveHighlights(curStep, prevStep) {
        if (Array.isArray(curStep.highlight) && curStep.highlight.length > 0) {
            return curStep.highlight.slice();
        }
        if (!prevStep) return [];
        return computeAutoDiff(curStep.diagram, prevStep.diagram);
    }

    function augmentDiagramWithHighlights(diagramSrc, highlightIds) {
        diagramSrc = diagramSource(diagramSrc);
        if (!highlightIds || highlightIds.length === 0) return diagramSrc;
        const safe = highlightIds.filter((id) => /^[A-Za-z_][A-Za-z0-9_-]*$/.test(id));
        if (safe.length === 0) return diagramSrc;
        return diagramSrc + "\n" +
            "classDef newNode stroke:#f59e0b,stroke-width:2.8px;\n" +
            `class ${safe.join(",")} newNode;`;
    }

    function escapeHtmlLabel(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function compactTypeText(text) {
        return String(text || "")
            .replace(/\\n/g, " ")
            .replace(/<[^>]*>/g, " ")
            .replace(/[^A-Za-z0-9]+/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
    }

    function inferNodeType(id, label, shape) {
        const text = `${compactTypeText(id)} ${compactTypeText(label)}`;
        const has = (re) => re.test(text);

        if (has(/\b(web servers?)\b/)) return "webserver";
        if (has(/\b(cdn|edge)\b/)) return "edge";
        if (has(/\b(geo ?dns|dns)\b/)) return "dns";
        if (has(/\b(load balancer|balancer|\blb\b)\b/)) return "load balancer";
        if (has(/\bapi gateway\b/) || has(/\bapi\b/) || has(/\b(endpoint|graphql)\b/)) return "api";
        if (has(/\b(router|gateway)\b/)) return "router";
        if (has(/\b(queue|stream|event bus|message bus|topic|log)\b/) || shape === "subroutine" && has(/\bq\b/)) return "queue";
        if (has(/\b(cache|redis|memcached)\b/)) return "cache";
        if (has(/\b(object storage|media store|archive|origin|bucket|storage engine|commit logs?|memtables?|sstables?|hash table|blob store|file store)\b/)) return "storage";
        if (has(/\b(index|search index|owner index|analytics store)\b/)) return "index";
        if (has(/\b(db|database|datastore|data store|store|shard|replica|primary|master|slave|sql|nosql|kv)\b/) || shape === "database") return "database";
        if (has(/\b(worker|processor|scheduler|parser|normalizer|filter|classifier|fingerprinter|compactor|controller|merge|jobs)\b/)) return "worker";
        if (has(/\b(generator|allocator|id gen|idgen)\b/)) return "generator";
        if (has(/\b(auth|rate limit|limiter|policy|rules?)\b/)) return "policy";
        if (has(/\b(metrics?|alerts?|dashboard|logs?|analytics|tools|observability)\b/)) return "observability";
        if (has(/\b(service|server|app|web tier|post svc|feed svc|user svc)\b/)) return "service";
        if (has(/\b(workers?)\b/)) return "worker";
        if (has(/\b(client|user|viewer|author|browser|mobile|operator|admin)\b/)) return "client";
        if (has(/\b(graph|social graph)\b/)) return "graph";
        return "";
    }

    const NODE_TYPE_STYLES = {
        webserver: {className: "nodeTypeWebserver", fill: "#fff7ed", stroke: "#ea580c"},
        edge: {className: "nodeTypeEdge", fill: "#eff6ff", stroke: "#2563eb"},
        dns: {className: "nodeTypeDns", fill: "#eff6ff", stroke: "#2563eb"},
        "load balancer": {className: "nodeTypeLoadBalancer", fill: "#fff7ed", stroke: "#ea580c"},
        queue: {className: "nodeTypeQueue", fill: "#f5f3ff", stroke: "#7c3aed"},
        cache: {className: "nodeTypeCache", fill: "#ecfdf5", stroke: "#059669"},
        storage: {className: "nodeTypeStorage", fill: "#eef2ff", stroke: "#4f46e5"},
        index: {className: "nodeTypeIndex", fill: "#eef2ff", stroke: "#4f46e5"},
        database: {className: "nodeTypeDatabase", fill: "#eef2ff", stroke: "#4f46e5"},
        worker: {className: "nodeTypeWorker", fill: "#fff7ed", stroke: "#ea580c"},
        router: {className: "nodeTypeRouter", fill: "#fff7ed", stroke: "#ea580c"},
        generator: {className: "nodeTypeGenerator", fill: "#fffbeb", stroke: "#d97706"},
        policy: {className: "nodeTypePolicy", fill: "#fef2f2", stroke: "#dc2626"},
        observability: {className: "nodeTypeObservability", fill: "#f0fdfa", stroke: "#0f766e"},
        api: {className: "nodeTypeApi", fill: "#eff6ff", stroke: "#2563eb"},
        service: {className: "nodeTypeService", fill: "#fff7ed", stroke: "#ea580c"},
        client: {className: "nodeTypeClient", fill: "#f8fafc", stroke: "#64748b"},
        graph: {className: "nodeTypeGraph", fill: "#fdf4ff", stroke: "#c026d3"},
    };

    function nodeTypeStyle(type) {
        return NODE_TYPE_STYLES[type] || null;
    }

    function typeAnnotatedLabel(type, label) {
        // The node label may carry an annotation: the first `\n`-separated segment
        // is the node name (rendered as the main label); any following segments are
        // an explanatory note rendered smaller, greyer, and in parentheses.
        const segments = String(label).split(/\\n/);
        const name = segments.shift();
        const body = escapeHtmlLabel(name).replace(/\\n/g, "<br/>");
        const noteText = segments.join("\n").trim();
        const note = noteText
            ? `<span class='node-annotation' style='display:block;margin-top:2px;color:#8a929e;font-size:9px;line-height:1.1;font-weight:400;'>(${escapeHtmlLabel(noteText).replace(/\n/g, "<br/>")})</span>`
            : "";
        const topSpacer = (type === "database" || type === "storage" || type === "index")
            ? "<span class='node-label-top-spacer' style='display:block;height:1em;line-height:1em;'>&nbsp;</span>"
            : "";
        const caption = type
            ? `<span class='node-type-caption' style='display:block;margin:0 0 1px;color:#6a7280;font-size:10px;line-height:1;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;'>${escapeHtmlLabel(type)}</span>`
            : "";
        return `<span class='node-label-stack' style='display:inline-block;line-height:1.12;text-align:center;white-space:nowrap;'>${topSpacer}${caption}<span class='node-main-label' style='display:block;line-height:1.15;'>${body}</span>${note}</span>`;
    }

    function annotateFlowchartNodeTypes(diagramSrc) {
        diagramSrc = diagramSource(diagramSrc);
        const firstLine = diagramSrc.split("\n").find((line) => line.trim());
        if (!/^\s*(graph|flowchart)\b/.test(firstLine || "")) return diagramSrc;

        const patterns = [
            {shape: "subroutine", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\[(.+)\]\](\s*)$/},
            {shape: "database", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\((.+)\)\](\s*)$/},
            {shape: "stadium", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\(\[(.+)\]\)(\s*)$/},
            {shape: "circle", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\(\((.+)\)\)(\s*)$/},
            {shape: "diamond", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\{(.+)\}(\s*)$/},
            {shape: "parallelogram", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\/(.+)\/\](\s*)$/},
            {shape: "asymmetric", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)>(.+)\](\s*)$/},
            {shape: "rect", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[(.+)\](\s*)$/},
        ];

        const typeClasses = new Map();

        function rememberTypeClass(id, type) {
            const style = nodeTypeStyle(type);
            if (!style) return;
            if (!typeClasses.has(style.className)) typeClasses.set(style.className, {style, ids: []});
            typeClasses.get(style.className).ids.push(id);
        }

        function rebuild(shape, id, label) {
            const type = inferNodeType(id, label, shape);
            if (/node-type-caption/.test(label)) return null;
            // Rebuild when the node has a known type OR carries an inline annotation
            // (a `\n` in the label), so annotation styling reaches typeless nodes too.
            const hasAnnotation = /\\n/.test(label);
            if (!type && !hasAnnotation) return null;
            if (type) rememberTypeClass(id, type);
            const annotated = typeAnnotatedLabel(type, label);
            // Caches are visually distinct from authoritative databases/stores:
            // render them as stadium/pill nodes even if the source uses DB syntax.
            const renderedShape = type === "cache" ? "stadium" : shape;
            switch (renderedShape) {
                case "subroutine":
                    return `${id}[["${annotated}"]]`;
                case "database":
                    return `${id}[("${annotated}")]`;
                case "stadium":
                    return `${id}(["${annotated}"])`;
                case "circle":
                    return `${id}(("${annotated}"))`;
                case "diamond":
                    return `${id}{"${annotated}"}`;
                case "parallelogram":
                    return `${id}[/"${annotated}"/]`;
                case "asymmetric":
                    return `${id}>"${annotated}"]`;
                default:
                    return `${id}["${annotated}"]`;
            }
        }

        const annotatedLines = diagramSrc.split("\n").map((line) => {
            if (/^\s*(classDef|class|style|linkStyle|click)\b/.test(line)) return line;
            for (const p of patterns) {
                const m = line.match(p.re);
                if (!m) continue;
                const rebuilt = rebuild(p.shape, m[2], m[3].trim());
                return rebuilt ? `${m[1]}${rebuilt}${m[4]}` : line;
            }
            return line;
        });

        if (typeClasses.size === 0) return annotatedLines.join("\n");

        const classLines = [];
        typeClasses.forEach(({style, ids}, className) => {
            const uniqueIds = [...new Set(ids)];
            classLines.push(`classDef ${className} fill:${style.fill},stroke:#d1d5db,stroke-width:1.4px,color:#1f2329;`);
            classLines.push(`class ${uniqueIds.join(",")} ${className};`);
        });

        return annotatedLines.concat(classLines).join("\n");
    }

    // Extract participant IDs from a Mermaid sequenceDiagram source. Recognizes:
    //   participant X
    //   participant X as Label
    //   actor X (as ...)
    //   bare message lines: X->>Y: msg  /  X-)Y: msg  /  X-->>Y: msg  /  X-xY  etc.
    // Returns a Set of bare identifiers.
    function extractSequenceParticipants(diagram) {
        diagram = diagramSource(diagram);
        if (!diagram) return new Set();
        const ids = new Set();
        // Participant IDs in sequence diagrams are alphanumeric + underscore. Avoid
        // hyphens in the character class so we don't accidentally swallow a `-` from
        // the arrow (`-->>`, `-x`, `-)`).
        const reDecl = /^\s*(?:participant|actor)\s+([A-Za-z_][A-Za-z0-9_]*)/gm;
        let m;
        while ((m = reDecl.exec(diagram)) !== null) ids.add(m[1]);
        // Sequence message arrows. Mermaid supports ->, -->, ->>, -->>, -x, --x,
        // -), --), and dotted variants. We just need the two endpoint identifiers.
        const reMsg = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:--?>>?|--?x|--?\))\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/gm;
        while ((m = reMsg.exec(diagram)) !== null) {
            ids.add(m[1]);
            ids.add(m[2]);
        }
        const reserved = new Set([
            "sequenceDiagram", "participant", "actor", "Note", "note", "loop",
            "alt", "else", "opt", "par", "and", "rect", "activate", "deactivate",
            "end", "autonumber", "title", "over", "left", "right", "of",
            "classDef", "class",
        ]);
        for (const r of reserved) ids.delete(r);
        return ids;
    }

    // Resolve which participants in `flow` should be highlighted at `currentStep`.
    // Strategy:
    //   - If flow.highlight is an explicit array, use it (filtered to known IDs).
    //   - Otherwise union:
    //       a) participants new to this step (not present in any earlier step's flows), and
    //       b) participants whose ID matches a node in currentStep.highlight (inheritance).
    function resolveFlowHighlights(flow, currentStep, allStepsBefore) {
        const flowParticipants = extractSequenceParticipants(flow.diagram);

        if (Array.isArray(flow.highlight) && flow.highlight.length > 0) {
            // Only keep IDs that actually appear in the flow, so a typo or stale
            // reference doesn't inject orphan `class` lines.
            return flow.highlight.filter((id) => flowParticipants.has(id));
        }

        const out = new Set();

        // (a) Diff against the union of all previous steps' flow participants.
        const seenBefore = new Set();
        for (const prev of allStepsBefore) {
            const flows = Array.isArray(prev.flows) ? prev.flows : [];
            for (const f of flows) {
                if (!f || !hasDiagram(f.diagram)) continue;
                for (const id of extractSequenceParticipants(f.diagram)) seenBefore.add(id);
            }
        }
        for (const id of flowParticipants) {
            if (!seenBefore.has(id)) out.add(id);
        }

        // (b) Inherit step.highlight matches that appear as participants here.
        const stepHighlight = Array.isArray(currentStep.highlight) ? currentStep.highlight : [];
        for (const id of stepHighlight) {
            if (flowParticipants.has(id)) out.add(id);
        }

        return [...out];
    }

    function splitIntoSentences(text) {
        const t = String(text).trim();
        if (!t) return [];
        const ABBREVS = /(?:e\.g|i\.e|etc|vs|cf|approx|Mr|Mrs|Ms|Dr|St|Jr|Sr|No|Fig|al)$/i;
        const out = [];
        const re = /([.!?])(\s+)(?=[A-Z0-9])/g;
        let last = 0;
        let m;
        while ((m = re.exec(t)) !== null) {
            const end = m.index + 1;
            const sentence = t.slice(last, end);
            const lastWord = sentence.match(/(\S+)\.$/);
            if (lastWord && ABBREVS.test(lastWord[1].replace(/\.$/, ""))) continue;
            out.push(sentence.trim());
            last = end + m[2].length;
        }
        const tail = t.slice(last).trim();
        if (tail) out.push(tail);
        return out;
    }

    function bulletsFrom(description) {
        if (Array.isArray(description)) {
            return description.map((s) => String(s).trim()).filter(Boolean);
        }
        if (typeof description === "string") return splitIntoSentences(description);
        return [];
    }

    function makeBulletList(items, className) {
        const ul = document.createElement("ul");
        if (className) ul.className = className;
        for (const item of items) {
            const li = document.createElement("li");
            li.textContent = String(item);
            ul.appendChild(li);
        }
        return ul;
    }

    // ---------- Entries (sidebar model) ----------

    function buildEntries(data) {
        const entries = [];
        if (data.requirements) {
            entries.push({kind: "intro", id: INTRO_SLUGS.requirements, title: "Requirements", payload: data.requirements});
        }
        if (Array.isArray(data.capacity) && data.capacity.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.capacity, title: "Capacity Estimation", payload: data.capacity});
        }
        if (Array.isArray(data.api) && data.api.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.api, title: "API Design", payload: data.api});
        }
        if (Array.isArray(data.dataModel) && data.dataModel.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.dataModel, title: "Data Model", payload: data.dataModel});
        }
        if (Array.isArray(data.patterns) && data.patterns.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.patterns, title: "Patterns", payload: data.patterns});
        }
        if (Array.isArray(data.patternCatalog) && data.patternCatalog.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.patternCatalog, title: "Pattern Catalog", payload: data.patternCatalog});
        }
        if (Array.isArray(data.steps)) {
            for (const step of data.steps) entries.push({kind: "step", id: step.id, title: step.title, payload: step});
        }
        const finalDesign = resolveFinalDesign(data);
        if (finalDesign) {
            entries.push({
                kind: "intro",
                id: INTRO_SLUGS.finalDesign,
                title: "Final Design",
                payload: finalDesign,
            });
        }
        if (Array.isArray(data.api) && data.api.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.apiFlows, title: "API Flows", payload: data.api});
        }
        if (data.satisfies && typeof data.satisfies === "object" && (
            (Array.isArray(data.satisfies.functional) && data.satisfies.functional.length > 0) ||
            (Array.isArray(data.satisfies.nonFunctional) && data.satisfies.nonFunctional.length > 0)
        )) {
            entries.push({kind: "intro", id: INTRO_SLUGS.satisfies, title: "Design vs. Requirements", payload: data.satisfies});
        }
        if (Array.isArray(data.interviewScript) && data.interviewScript.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.interviewScript, title: "Interview Script", payload: data.interviewScript});
        }
        if (Array.isArray(data.levelVariants) && data.levelVariants.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.levelVariants, title: "By Level", payload: data.levelVariants});
        }
        if (Array.isArray(data.followUps) && data.followUps.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.followUps, title: "Follow-up Questions", payload: data.followUps});
        }
        return entries;
    }

    function resolveFinalDesign(data) {
        if (data && data.finalDesign && hasStepLikeDiagram(data.finalDesign)) {
            return Object.assign({title: "Final Design"}, data.finalDesign);
        }
        return null;
    }

    function renderNav() {
        els.navList.innerHTML = "";

        const introEntries = state.entries.filter((e) => e.kind === "intro");
        const stepEntries = state.entries.filter((e) => e.kind === "step");

        // Steps may declare an optional `parent: '<other-step-id>'` to mark
        // themselves as a sub-step (a smaller working of one aspect of the parent).
        // We render those indented in the sidebar.
        const knownStepIds = new Set(stepEntries.map((e) => e.id));

        function makeGroup(label, items) {
            if (items.length === 0) return;
            const header = document.createElement("div");
            header.className = "nav-group";
            header.textContent = label;
            els.navList.appendChild(header);

            const ul = document.createElement("ol");
            ul.className = "nav-items";
            items.forEach((entry) => {
                const idx = state.entries.indexOf(entry);
                const li = document.createElement("li");
                li.textContent = entry.title;
                li.dataset.entryIndex = String(idx);
                if (idx === state.currentEntryIndex) li.classList.add("active");
                if (
                    entry.kind === "step" &&
                    entry.payload &&
                    typeof entry.payload.parent === "string" &&
                    knownStepIds.has(entry.payload.parent)
                ) {
                    li.classList.add("nav-item-child");
                }
                li.addEventListener("click", () => selectEntry(idx));
                ul.appendChild(li);
            });
            els.navList.appendChild(ul);
        }

        makeGroup("Overview", introEntries.filter((e) => !WRAPUP_SLUGS.has(e.id)));
        makeGroup("High-Level Architecture", stepEntries);
        const wrapupEntries = WRAPUP_ORDER
            .map((slug) => introEntries.find((e) => e.id === slug))
            .filter(Boolean);
        makeGroup("Wrap-up", wrapupEntries);
    }

    function updateNavActive() {
        const items = els.navList.querySelectorAll("li[data-entry-index]");
        items.forEach((li) => {
            li.classList.toggle("active", Number(li.dataset.entryIndex) === state.currentEntryIndex);
        });
    }

    // ---------- Rendering: description ----------

    function renderTopDecisionPrompt(prompt) {
        const content = renderTextOrBullets(prompt, "education-card decision-prompt top-decision-prompt");
        if (!content) return null;
        return content;
    }

    function appendConceptLine(card, label, value) {
        if (!value) return;
        const p = document.createElement("p");
        p.className = "concept-line";
        const strong = document.createElement("strong");
        strong.textContent = `${label}: `;
        p.appendChild(strong);
        p.appendChild(document.createTextNode(String(value)));
        card.appendChild(p);
    }

    function renderTopConcepts(concepts) {
        if (!Array.isArray(concepts) || concepts.length === 0) return null;
        const cards = [];
        for (const concept of concepts) {
            const card = document.createElement("article");
            card.className = "concept-card";
            if (typeof concept === "string") {
                const p = document.createElement("p");
                p.textContent = concept;
                card.appendChild(p);
            } else if (concept && typeof concept === "object") {
                const term = concept.term || concept.name || concept.title || "Concept";
                const h = document.createElement("h4");
                h.textContent = term;
                card.appendChild(h);
                if (concept.definition || concept.description) {
                    const p = document.createElement("p");
                    p.className = "concept-definition";
                    p.textContent = concept.definition || concept.description;
                    card.appendChild(p);
                }
                appendConceptLine(card, "Why it matters", concept.whyItMatters || concept.why);
                appendConceptLine(card, "Example", concept.example);
            }
            if (card.children.length > 0) cards.push(card);
        }
        if (cards.length === 0) return null;

        const wrap = document.createElement("div");
        wrap.className = "step-concepts";
        const h = document.createElement("h3");
        h.textContent = "Concepts introduced";
        wrap.appendChild(h);
        const grid = document.createElement("div");
        grid.className = "concept-grid";
        cards.forEach((card) => grid.appendChild(card));
        wrap.appendChild(grid);
        return wrap;
    }

    function renderDescription(description, decisionPrompt, concepts) {
        els.stepDescription.innerHTML = "";
        const prompt = renderTopDecisionPrompt(decisionPrompt);
        if (prompt) els.stepDescription.appendChild(prompt);
        const conceptBlock = renderTopConcepts(concepts);
        if (conceptBlock) els.stepDescription.appendChild(conceptBlock);
        const items = bulletsFrom(description);
        if (items.length === 0) return;
        els.stepDescription.appendChild(makeBulletList(items, "bullets"));
    }

    // ---------- Rendering: architecture step diagram + options ----------

    function effectiveDiagramFor(step) {
        if (Array.isArray(step.options) && step.options.length > 0) {
            const opt = step.options[state.currentOptionIndex] || step.options[0];
            return {
                diagram: pickDiagram(opt.diagram, step.diagram),
                highlight: Array.isArray(opt.highlight) ? opt.highlight : step.highlight,
            };
        }
        return {diagram: pickDiagram(step.diagram), highlight: step.highlight};
    }

    function defaultDiagramFor(step) {
        if (!step) return "";
        if (Array.isArray(step.options) && step.options.length > 0) {
            return pickDiagram(step.options[0].diagram, step.diagram);
        }
        return pickDiagram(step.diagram);
    }

    function defaultEffectiveFor(step) {
        const diagram = defaultDiagramFor(step);
        return diagram ? {diagram} : null;
    }

    function isFlowchartDiagram(diagramSrc) {
        const firstLine = diagramSource(diagramSrc).split("\n").find((line) => line.trim());
        return /^\s*(graph|flowchart)\b/.test(firstLine || "");
    }

    function flowchartHeader(diagramSrc) {
        const firstLine = diagramSource(diagramSrc).split("\n").find((line) => line.trim());
        return /^\s*(graph|flowchart)\b/.test(firstLine || "") ? firstLine.trim() : "graph TB";
    }

    // Force a flowchart's layout direction regardless of how it was authored.
    // Requirements/capacity diagrams render left-to-right (LR); architecture
    // steps and the final design render top-to-bottom (TB). Rewrites the
    // direction token on the first `graph`/`flowchart` header line, preserving
    // any trailing `;`. Non-flowcharts (sequence, ER) pass through untouched.
    function forceFlowchartDirection(diagramSrc, direction) {
        const src = diagramSource(diagramSrc);
        if (!isFlowchartDiagram(src)) return src;
        const lines = src.split("\n");
        const i = lines.findIndex((line) => line.trim());
        if (i < 0) return src;
        // graph|flowchart [DIR] [;]  ->  keyword + forced direction (+ ;)
        lines[i] = lines[i].replace(
            /^(\s*)(graph|flowchart)\b[ \t]*(?:LR|RL|TB|BT|TD)?[ \t]*(;?)[ \t]*$/,
            (m, indent, keyword, semi) => `${indent}${keyword} ${direction}${semi}`
        );
        return lines.join("\n");
    }

    function flowchartNodeDefinition(line) {
        const patterns = [
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\((.+)\)\](\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\(\[(.+)\]\)(\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\[(.+)\]\](\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\(\((.+)\)\)(\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\{(.+)\}(\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[\/(.+)\/\](\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)>(.+)\](\s*)$/,
            /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[(.+)\](\s*)$/,
        ];
        for (const re of patterns) {
            const m = line.match(re);
            if (m) return {id: m[2], label: m[3].trim(), line};
        }
        return null;
    }

    function canonicalNodeConcept(id, label) {
        let text = compactTypeText(label || id);
        if (!text) return "";
        text = text
            .replace(/\bregion\s+[a-z0-9]+\b/g, " ")
            .replace(/\bzone\s+[a-z0-9]+\b/g, " ")
            .replace(/\baz\s+[a-z0-9]+\b/g, " ")
            .replace(/\b(instance|node|server)\s+\d+\b/g, "$1")
            .replace(/\b\d+\b/g, " ")
            .replace(/\b(apps|applications)\b/g, "app server")
            .replace(/\bapplication\s+servers?\b/g, "app server")
            .replace(/\bapp\s+servers?\b/g, "app server")
            .replace(/\bweb\s+servers?\b/g, "web server")
            .replace(/\bdb\s+shards?\b/g, "database")
            .replace(/\bdatabase\s+shards?\b/g, "database")
            .replace(/\bdatabases\b/g, "database")
            .replace(/\bservers\b/g, "server")
            .replace(/\bshards\b/g, "shard")
            .replace(/\bcaches\b/g, "cache")
            .replace(/\s+/g, " ")
            .trim();
        if (text === "app") return "app server";
        return text;
    }

    function flowchartEdgeDefinition(line) {
        const trimmed = line.trim();
        const m = trimmed.match(/^([A-Za-z_][A-Za-z0-9_-]*)\s*(?:--+>|--+|==+>|-\.-+>|<-+>|<--+)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)/);
        if (!m) return null;
        return {
            from: m[1],
            to: m[2],
            key: trimmed.replace(/\s+/g, " "),
            line,
        };
    }

    function mergeFlowchartSources(sources) {
        const usable = sources.map(diagramSource).filter(isFlowchartDiagram);
        if (usable.length === 0) return "";

        const nodeLines = new Map();
        const nodeConcepts = new Map();
        const conceptOwners = new Map();
        const edgeLines = [];
        const edgeKeys = new Set();
        const otherLines = [];
        const otherSeen = new Set();

        usable.forEach((src) => {
            const lines = src.split("\n");
            const sourceNodes = [];
            const sourceNodeIds = new Set();
            const sourceConcepts = new Set();

            lines.forEach((line) => {
                const node = flowchartNodeDefinition(line);
                if (!node) return;
                const concept = canonicalNodeConcept(node.id, node.label);
                sourceNodes.push(Object.assign(node, {concept}));
                sourceNodeIds.add(node.id);
                if (concept) sourceConcepts.add(concept);
            });

            sourceConcepts.forEach((concept) => {
                const owners = conceptOwners.get(concept) || new Set();
                owners.forEach((oldId) => {
                    if (sourceNodeIds.has(oldId)) return;
                    nodeLines.delete(oldId);
                    nodeConcepts.delete(oldId);
                    owners.delete(oldId);
                });
                if (owners.size === 0) conceptOwners.delete(concept);
            });

            lines.forEach((line) => {
                const trimmed = line.trim();
                if (!trimmed) return;
                if (/^(graph|flowchart)\b/.test(trimmed)) return;
                if (/^(classDef|class|style|linkStyle|click)\b/.test(trimmed)) return;
                if (/^(subgraph|end|direction)\b/.test(trimmed)) {
                    if (!otherSeen.has(trimmed)) {
                        otherSeen.add(trimmed);
                        otherLines.push(line);
                    }
                    return;
                }
                const edge = flowchartEdgeDefinition(line);
                if (edge) {
                    if (!edgeKeys.has(edge.key)) {
                        edgeKeys.add(edge.key);
                        edgeLines.push(edge);
                    }
                    return;
                }
                const node = sourceNodes.find((n) => n.line === line);
                if (node) {
                    const oldConcept = nodeConcepts.get(node.id);
                    if (oldConcept && conceptOwners.has(oldConcept)) {
                        conceptOwners.get(oldConcept).delete(node.id);
                    }
                    nodeLines.set(node.id, line);
                    if (node.concept) {
                        nodeConcepts.set(node.id, node.concept);
                        if (!conceptOwners.has(node.concept)) conceptOwners.set(node.concept, new Set());
                        conceptOwners.get(node.concept).add(node.id);
                    }
                    return;
                }
                if (!otherSeen.has(trimmed)) {
                    otherSeen.add(trimmed);
                    otherLines.push(line);
                }
            });
        });

        return [
            flowchartHeader(usable[usable.length - 1]),
            ...otherLines,
            ...nodeLines.values(),
            ...edgeLines.filter((edge) => nodeLines.has(edge.from) && nodeLines.has(edge.to)).map((edge) => edge.line),
        ].join("\n");
    }

    function fullContextDiagramFor(entryIndex, currentDiagram) {
        const entry = state.entries[entryIndex];
        if (!entry || entry.kind !== "step") return currentDiagram;
        const sources = [];
        for (let i = 0; i < entryIndex; i++) {
            const prev = state.entries[i];
            if (prev && prev.kind === "step") {
                const diagram = defaultDiagramFor(prev.payload);
                if (diagram) sources.push(diagram);
            }
        }
        if (currentDiagram) sources.push(currentDiagram);
        const merged = mergeFlowchartSources(sources);
        return merged || currentDiagram;
    }

    async function renderDiagram(diagramSrc, explicitHighlight, prevStep) {
        clearError();
        const tempStep = {diagram: diagramSrc, highlight: explicitHighlight};
        const prevEffective = prevStep
            ? defaultEffectiveFor(prevStep)
            : null;
        const highlights = resolveHighlights(tempStep, prevEffective);
        // Architecture steps and the final design always lay out top-to-bottom.
        const directedSrc = forceFlowchartDirection(diagramSrc || "", "TB");
        const displaySrc = annotateFlowchartNodeTypes(directedSrc);
        const src = augmentDiagramWithHighlights(displaySrc, highlights);

        const renderId = `mermaid-svg-${Date.now()}`;
        try {
            const {svg, bindFunctions} = await mermaid.render(renderId, src);
            els.diagram.innerHTML = svg;
            if (bindFunctions) bindFunctions(els.diagram);
        } catch (err) {
            els.diagram.innerHTML = "";
            showError(`Mermaid render error: ${err.message || err}`);
        }
    }

    function renderDiagramViewTabs(entry) {
        els.diagramViewTabs.innerHTML = "";
        const show = entry && entry.kind === "step";
        els.diagramBlock.classList.toggle("has-diagram-view-tabs", show);
        if (!show) {
            els.diagramViewTabs.hidden = true;
            state.currentDiagramView = "focus";
            return;
        }

        if (state.currentDiagramView !== "focus" && state.currentDiagramView !== "context") {
            state.currentDiagramView = "focus";
        }

        els.diagramViewTabs.hidden = false;
        [
            {id: "focus", label: "Step focus"},
            {id: "context", label: "Full context"},
        ].forEach((view) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "diagram-view-tab" + (view.id === state.currentDiagramView ? " active" : "");
            btn.textContent = view.label;
            btn.setAttribute("role", "tab");
            btn.setAttribute("aria-selected", view.id === state.currentDiagramView ? "true" : "false");
            btn.addEventListener("click", () => selectDiagramView(view.id));
            els.diagramViewTabs.appendChild(btn);
        });
    }

    function renderOptionTabs(step) {
        els.optionTabs.innerHTML = "";
        if (!Array.isArray(step.options) || step.options.length === 0) {
            els.optionTabs.hidden = true;
            return;
        }
        els.optionTabs.hidden = false;
        step.options.forEach((opt, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "option-tab" + (idx === state.currentOptionIndex ? " active" : "");
            btn.textContent = `${idx + 1}. ${opt.name || "Option"}`;
            btn.setAttribute("role", "tab");
            btn.setAttribute("aria-selected", idx === state.currentOptionIndex ? "true" : "false");
            btn.addEventListener("click", () => selectOption(idx));
            els.optionTabs.appendChild(btn);
        });
    }

    function renderProsCons(step) {
        els.optionProsCons.innerHTML = "";
        if (!Array.isArray(step.options) || step.options.length === 0) {
            els.optionProsCons.hidden = true;
            return;
        }
        const opt = step.options[state.currentOptionIndex] || step.options[0];
        const pros = Array.isArray(opt.pros) ? opt.pros : [];
        const cons = Array.isArray(opt.cons) ? opt.cons : [];
        if (pros.length === 0 && cons.length === 0) {
            els.optionProsCons.hidden = true;
            return;
        }
        els.optionProsCons.hidden = false;

        function col(label, items, cls) {
            const c = document.createElement("div");
            c.className = `proscons-col ${cls}`;
            const h = document.createElement("h3");
            h.textContent = label;
            c.appendChild(h);
            c.appendChild(makeBulletList(items));
            return c;
        }

        if (pros.length > 0) els.optionProsCons.appendChild(col("Pros", pros, "pros"));
        if (cons.length > 0) els.optionProsCons.appendChild(col("Cons", cons, "cons"));
    }

    // ---------- Rendering: per-step extras ----------

    function makeSection(title, contentEl, className) {
        const wrap = document.createElement("section");
        wrap.className = `extras-section${className ? " " + className : ""}`;
        const h = document.createElement("h3");
        h.textContent = title;
        wrap.appendChild(h);
        wrap.appendChild(contentEl);
        return wrap;
    }

    function makeLabeledText(label, value) {
        const wrap = document.createElement("div");
        wrap.className = "labeled-text";
        const h = document.createElement("h4");
        h.textContent = label;
        wrap.appendChild(h);
        const p = document.createElement("p");
        p.textContent = String(value || "");
        wrap.appendChild(p);
        return wrap;
    }

    function renderTextOrBullets(value, className) {
        const items = bulletsFrom(value);
        const wrap = document.createElement("div");
        if (className) wrap.className = className;
        if (items.length === 0) return null;
        if (items.length === 1) {
            const p = document.createElement("p");
            p.textContent = items[0];
            wrap.appendChild(p);
        } else {
            wrap.appendChild(makeBulletList(items));
        }
        return wrap;
    }

    function renderWhyNow(whyNow) {
        const content = renderTextOrBullets(whyNow, "education-card");
        return content ? makeSection("Why now", content, "why-now") : null;
    }

    function renderRecap(recap) {
        if (!recap) return null;
        if (typeof recap === "string" || Array.isArray(recap)) {
            const content = renderTextOrBullets(recap, "education-card");
            return content ? makeSection("Recap", content, "recap") : null;
        }

        const fields = [
            ["Before", recap.before],
            ["After", recap.after],
            ["New risk", recap.newRisk],
        ].filter((pair) => pair[1]);
        if (fields.length === 0) return null;

        const wrap = document.createElement("div");
        wrap.className = "recap-grid";
        fields.forEach(([label, value]) => {
            wrap.appendChild(makeLabeledText(label, value));
        });
        return makeSection("Recap", wrap, "recap");
    }

    function renderFailureDrills(drills) {
        if (!Array.isArray(drills) || drills.length === 0) return null;
        const wrap = document.createElement("div");
        wrap.className = "failure-drill-list";
        for (const drill of drills) {
            if (!drill) continue;
            const card = document.createElement("div");
            card.className = "failure-drill-card";
            const scenario = drill.scenario || drill.title || "Failure scenario";
            const h = document.createElement("h4");
            h.textContent = scenario;
            card.appendChild(h);
            if (drill.expectedBehavior || drill.expected) {
                card.appendChild(makeLabeledText("Expected behavior", drill.expectedBehavior || drill.expected));
            }
            if (drill.mitigation || drill.recovery) {
                card.appendChild(makeLabeledText("Mitigation", drill.mitigation || drill.recovery));
            }
            if (drill.lesson || drill.teachingPoint) {
                card.appendChild(makeLabeledText("Teaching point", drill.lesson || drill.teachingPoint));
            }
            wrap.appendChild(card);
        }
        return wrap.children.length > 0 ? makeSection("Failure drills", wrap, "failure-drills") : null;
    }

    // Per-step common traps. Each item: { trap, why?, instead? }.
    // The mistake, why it's wrong, and the better move — the book's "common
    // traps" differentiator, scoped to the step where the trap arises.
    function renderTraps(traps) {
        if (!Array.isArray(traps) || traps.length === 0) return null;
        const wrap = document.createElement("div");
        wrap.className = "trap-list";
        for (const t of traps) {
            if (!t) continue;
            const card = document.createElement("div");
            card.className = "trap-card";
            const h = document.createElement("h4");
            h.textContent = t.trap || t.title || "Trap";
            card.appendChild(h);
            if (t.why) card.appendChild(makeLabeledText("Why it's wrong", t.why));
            if (t.instead || t.better) card.appendChild(makeLabeledText("Do instead", t.instead || t.better));
            wrap.appendChild(card);
        }
        return wrap.children.length > 0 ? makeSection("Common traps", wrap, "traps") : null;
    }

    // Per-step pattern tags: string IDs/names rendered as chips. Surfaces the
    // reusable patterns (see Overview > Patterns) exercised by this step.
    function renderStepPatternTags(patterns) {
        if (!Array.isArray(patterns) || patterns.length === 0) return null;
        const wrap = document.createElement("div");
        wrap.className = "pattern-tags";
        for (const p of patterns) {
            const chip = document.createElement("span");
            chip.className = "pattern-tag";
            chip.textContent = String(p);
            wrap.appendChild(chip);
        }
        return makeSection("Patterns", wrap, "step-patterns");
    }

    function renderInterviewerSignals(signals) {
        if (!signals || typeof signals !== "object") return null;
        const strong = bulletsFrom(signals.strong || []);
        const weak = bulletsFrom(signals.weak || []);
        if (strong.length === 0 && weak.length === 0) return null;

        const wrap = document.createElement("div");
        wrap.className = "signal-columns";
        if (strong.length > 0) {
            const col = document.createElement("div");
            col.className = "signal-col strong";
            const h = document.createElement("h4");
            h.textContent = "Strong signals";
            col.appendChild(h);
            col.appendChild(makeBulletList(strong));
            wrap.appendChild(col);
        }
        if (weak.length > 0) {
            const col = document.createElement("div");
            col.className = "signal-col weak";
            const h = document.createElement("h4");
            h.textContent = "Weak signals";
            col.appendChild(h);
            col.appendChild(makeBulletList(weak));
            wrap.appendChild(col);
        }
        return makeSection("Interviewer signals", wrap, "signals");
    }

    function appendStepExtra(section) {
        if (section) els.stepExtras.appendChild(section);
    }

    function renderStepExtras(step) {
        els.stepExtras.innerHTML = "";

        appendStepExtra(renderStepPatternTags(step.patterns));

        if (Array.isArray(step.flows) && step.flows.length > 0) {
            // Only render valid flows (must have a non-empty diagram source).
            const validFlows = step.flows.filter(
                (f) => f && hasDiagram(f.diagram)
            );
            if (validFlows.length > 0) {
                if (state.currentFlowIndex >= validFlows.length) state.currentFlowIndex = 0;

                // Steps strictly before the current one — used to diff "new" participants.
                const stepEntries = state.entries.filter((e) => e.kind === "step");
                let currentStepIdx = stepEntries.findIndex((e) => e.payload === step);
                if (currentStepIdx < 0) currentStepIdx = stepEntries.length;
                const allStepsBefore = stepEntries.slice(0, Math.max(0, currentStepIdx)).map((e) => e.payload);

                const wrap = document.createElement("div");
                wrap.className = "flow-tabs-wrap";

                // Tabs row
                const tabs = document.createElement("div");
                tabs.className = "flow-tabs";
                tabs.setAttribute("role", "tablist");
                validFlows.forEach((flow, idx) => {
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "flow-tab" + (idx === state.currentFlowIndex ? " active" : "");
                    btn.textContent = flow.name || `Flow ${idx + 1}`;
                    btn.setAttribute("role", "tab");
                    btn.setAttribute("aria-selected", idx === state.currentFlowIndex ? "true" : "false");
                    btn.addEventListener("click", () => selectFlow(idx));
                    tabs.appendChild(btn);
                });
                wrap.appendChild(tabs);

                // Selected flow's body
                const flow = validFlows[state.currentFlowIndex];
                const body = document.createElement("div");
                body.className = "flow-body";
                if (flow.note) {
                    const n = document.createElement("p");
                    n.className = "flow-note muted";
                    n.textContent = flow.note;
                    body.appendChild(n);
                }
                const flowHighlights = resolveFlowHighlights(flow, step, allStepsBefore);
                const flowSrc = diagramSource(flow.diagram);
                body.appendChild(makeMermaidEl(flowSrc, "flow-diagram", {
                    highlightParticipants: flowHighlights,
                    sourceForLabels: flowSrc,
                    annotateParticipants: true,
                }));
                wrap.appendChild(body);

                els.stepExtras.appendChild(makeSection("Flows", wrap, "flows"));
            }
        }

        appendStepExtra(renderWhyNow(step.whyNow));
        appendStepExtra(renderRecap(step.recap));
        appendStepExtra(renderFailureDrills(step.failureDrills));
        appendStepExtra(renderTraps(step.traps));

        if (Array.isArray(step.deepDives) && step.deepDives.length > 0) {
            const wrap = document.createElement("div");
            wrap.className = "deepdive-list";
            for (const dd of step.deepDives) {
                const card = document.createElement("div");
                card.className = "deepdive-card";
                const h = document.createElement("h4");
                h.textContent = dd.title || "Deep dive";
                card.appendChild(h);
                card.appendChild(makeBulletList(bulletsFrom(dd.points || [])));
                // Optional escape hatch: a deep dive may carry its own diagram for the
                // rare structural detail the main/option/flow diagrams don't cover.
                if (hasDiagram(dd.diagram)) {
                    const ddSrc = diagramSource(dd.diagram);
                    card.appendChild(makeMermaidEl(ddSrc, "deepdive-diagram", {
                        annotateParticipants: true,
                        sourceForLabels: ddSrc,
                    }));
                }
                wrap.appendChild(card);
            }
            els.stepExtras.appendChild(makeSection("Deep dives", wrap, "deepdives"));
        }

        if (Array.isArray(step.bottlenecks) && step.bottlenecks.length > 0) {
            const table = document.createElement("div");
            table.className = "bottleneck-list";
            for (const b of step.bottlenecks) {
                const row = document.createElement("div");
                row.className = "bottleneck-row";
                const issue = document.createElement("div");
                issue.className = "bottleneck-issue";
                issue.textContent = b.issue || "";
                const mit = document.createElement("div");
                mit.className = "bottleneck-mitigation";
                mit.textContent = b.mitigation || "";
                row.appendChild(issue);
                row.appendChild(mit);
                table.appendChild(row);
            }
            els.stepExtras.appendChild(makeSection("Bottlenecks & mitigations", table, "bottlenecks"));
        }

        if (Array.isArray(step.talkingPoints) && step.talkingPoints.length > 0) {
            els.stepExtras.appendChild(makeSection("Talking points", makeBulletList(step.talkingPoints), "talking"));
        }

        appendStepExtra(renderInterviewerSignals(step.interviewerSignals));

        if (Array.isArray(step.followUps) && step.followUps.length > 0) {
            els.stepExtras.appendChild(makeSection("Follow-up questions", makeBulletList(step.followUps), "followups"));
        }
    }

    // ---------- Rendering: intro pages ----------

    // Counter so each Mermaid render has a unique id (Mermaid requires it).
    let mermaidIdSeq = 0;

    // Look up the participant id <-> label mapping declared in a sequence
    // diagram source so we can find rendered boxes by either name.
    function parseSequenceParticipantLabels(diagram) {
        const map = new Map(); // id -> label (or id if no "as ...")
        diagram = diagramSource(diagram);
        if (!diagram) return map;
        const re = /^\s*(?:participant|actor)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+(.+?))?\s*$/gm;
        let m;
        while ((m = re.exec(diagram)) !== null) {
            const id = m[1];
            const label = (m[2] || "").trim() || id;
            map.set(id, label);
        }
        return map;
    }

    // After Mermaid renders a sequence diagram, walk the SVG to find participant
    // boxes by their visible label and tag them with the `newNode` class so the
    // CSS in styles.css picks them up. We need this because Mermaid's sequence
    // parser rejects the `classDef` / `class` syntax we use for flowcharts.
    function applySequenceHighlights(targetEl, idToLabel, highlightIds) {
        if (!highlightIds || highlightIds.length === 0) return;
        const labels = new Set();
        for (const id of highlightIds) {
            if (idToLabel.has(id)) labels.add(idToLabel.get(id));
            labels.add(id); // also match the bare id, in case it's used as label
        }
        const svg = targetEl.querySelector("svg");
        if (!svg) return;

        // Mermaid v10 renders each participant's box label as a <text> element.
        // The corresponding box is the nearest preceding <rect> with class "actor"
        // (or "actor-top"/"actor-bottom") inside the same <g> parent.
        const texts = svg.querySelectorAll("text");
        texts.forEach((t) => {
            const txt = (t.textContent || "").trim();
            if (!labels.has(txt)) return;
            // Find the actor rect that belongs to this label. Strategy: walk up to
            // the parent group, then look for a <rect> child with class containing
            // "actor". Also bold the text.
            t.classList.add("newNode");
            const parent = t.parentNode;
            if (parent && parent.querySelectorAll) {
                parent.querySelectorAll("rect").forEach((r) => {
                    r.classList.add("newNode");
                });
            }
            // Some Mermaid versions place the rect as a sibling rather than a child.
            let prev = t.previousElementSibling;
            while (prev) {
                if (prev.tagName && prev.tagName.toLowerCase() === "rect") {
                    prev.classList.add("newNode");
                    break;
                }
                prev = prev.previousElementSibling;
            }
        });
    }

    function actorRectsForText(textEl) {
        const rects = [];
        const parent = textEl.parentNode;
        if (parent && parent.querySelectorAll) {
            parent.querySelectorAll("rect").forEach((r) => {
                const cls = r.getAttribute("class") || "";
                if (/\bactor\b|\bactor-top\b|\bactor-bottom\b/.test(cls)) rects.push(r);
            });
        }
        let prev = textEl.previousElementSibling;
        while (prev) {
            if (prev.tagName && prev.tagName.toLowerCase() === "rect") {
                const cls = prev.getAttribute("class") || "";
                if (/\bactor\b|\bactor-top\b|\bactor-bottom\b/.test(cls)) rects.push(prev);
                break;
            }
            prev = prev.previousElementSibling;
        }
        return rects;
    }

    function applySequenceParticipantTypes(targetEl, idToLabel) {
        if (!idToLabel || idToLabel.size === 0) return;
        const svg = targetEl.querySelector("svg");
        if (!svg) return;

        const byLabel = new Map();
        idToLabel.forEach((label, id) => {
            byLabel.set(label, {id, label});
            byLabel.set(id, {id, label});
        });

        const ns = svg.namespaceURI || "http://www.w3.org/2000/svg";
        const texts = svg.querySelectorAll("text");
        texts.forEach((t) => {
            if (t.dataset && t.dataset.participantTypeAnnotated === "true") return;
            const txt = (t.textContent || "").trim();
            const participant = byLabel.get(txt);
            if (!participant) return;
            if (actorRectsForText(t).length === 0) return;

            const type = inferNodeType(participant.id, participant.label, "participant");
            if (!type) return;
            const style = nodeTypeStyle(type);
            const rects = actorRectsForText(t);
            if (style) {
                t.classList.add(style.className);
                rects.forEach((r) => r.classList.add(style.className));
            }

            const x = t.getAttribute("x");
            t.textContent = "";
            if (t.dataset) t.dataset.participantTypeAnnotated = "true";

            const typeLine = document.createElementNS(ns, "tspan");
            typeLine.textContent = type.toUpperCase();
            typeLine.setAttribute("class", "sequence-node-type-caption");
            if (x !== null) typeLine.setAttribute("x", x);
            // Mermaid centers the original participant label vertically. Pull the
            // first tspan up so the smaller type caption does not float too low.
            typeLine.setAttribute("dy", "-1.1em");

            const labelLine = document.createElementNS(ns, "tspan");
            labelLine.textContent = participant.label;
            labelLine.setAttribute("class", "sequence-node-main-label");
            if (x !== null) labelLine.setAttribute("x", x);
            labelLine.setAttribute("dy", "1.15em");

            t.appendChild(typeLine);
            t.appendChild(labelLine);
        });
    }

    // Returns a container element. The Mermaid render is kicked off async; if
    // it errors we replace the container's contents with an inline error block.
    //
    // The optional `opts` argument supports `{ highlightParticipants,
    // sourceForLabels, annotateParticipants }`
    // for sequence diagrams. We can't use Mermaid's `classDef`/`class` syntax
    // there (the sequence parser rejects it), so instead we patch the rendered
    // SVG to tag participant boxes whose label matches a highlighted id.
    function makeMermaidEl(diagramSrc, className, opts) {
        diagramSrc = diagramSource(diagramSrc);
        const renderSrc = annotateFlowchartNodeTypes(diagramSrc);
        const wrap = document.createElement("div");
        wrap.className = `overview-diagram${className ? " " + className : ""}`;
        const target = document.createElement("div");
        target.className = "mermaid";
        wrap.appendChild(target);

        const id = `mermaid-intro-${Date.now()}-${++mermaidIdSeq}`;
        mermaid.render(id, renderSrc).then(
            ({svg, bindFunctions}) => {
                target.innerHTML = svg;
                if (bindFunctions) bindFunctions(target);
                if (opts && (opts.annotateParticipants || (Array.isArray(opts.highlightParticipants) && opts.highlightParticipants.length > 0))) {
                    const labelMap = parseSequenceParticipantLabels(opts.sourceForLabels || diagramSrc);
                    if (Array.isArray(opts.highlightParticipants) && opts.highlightParticipants.length > 0) {
                        applySequenceHighlights(target, labelMap, opts.highlightParticipants);
                    }
                    if (opts.annotateParticipants) {
                        applySequenceParticipantTypes(target, labelMap);
                    }
                }
            },
            (err) => {
                target.innerHTML = "";
                const e = document.createElement("div");
                e.className = "diagram-inline-error";
                e.textContent = `Mermaid render error: ${err && err.message ? err.message : err}`;
                wrap.appendChild(e);
            }
        );
        return wrap;
    }

    // Build a Mermaid `erDiagram` source from the dataModel array. Relationships
    // are not inferred — only entities + fields. Field types are sanitized: ER
    // syntax only allows simple identifiers for the type, so we strip spaces and
    // punctuation. The original type stays visible via a 'note' comment column.
    function autoErDiagramFromDataModel(tables) {
        if (!Array.isArray(tables) || tables.length === 0) return null;

        function safeIdent(s) {
            return String(s).replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "x";
        }

        function safeType(s) {
            // erDiagram type token must match [A-Za-z][A-Za-z0-9_-]*. Take first word.
            const m = String(s || "string").match(/[A-Za-z][A-Za-z0-9_-]*/);
            return m ? m[0] : "string";
        }

        const lines = ["erDiagram"];
        for (const t of tables) {
            const name = safeIdent(t.name || "table");
            lines.push(`  ${name} {`);
            for (const f of t.fields || []) {
                const fname = safeIdent(f.name || "field");
                const ftype = safeType(f.type);
                // Mark PK heuristically: type mentions 'PK' or field name is 'id'/ends in '_id PK'
                const isPk = /PK\b/.test(f.type || "") || /^(id|short_code|event_id|user_id)$/i.test(fname);
                lines.push(`    ${ftype} ${fname}${isPk ? " PK" : ""}`);
            }
            lines.push("  }");
        }
        return lines.join("\n");
    }

    function renderIntroRequirements(req) {
        const outer = document.createElement("div");
        if (state.data && hasDiagram(state.data.requirementsDiagram)) {
            // Requirements diagrams lay out left-to-right.
            outer.appendChild(makeMermaidEl(forceFlowchartDirection(state.data.requirementsDiagram, "LR")));
        }
        const wrap = document.createElement("div");
        wrap.className = "req-columns";
        const fn = Array.isArray(req.functional) ? req.functional : [];
        const nfn = Array.isArray(req.nonFunctional) ? req.nonFunctional : [];

        function col(title, items) {
            const c = document.createElement("div");
            c.className = "req-col";
            const h = document.createElement("h3");
            h.textContent = title;
            c.appendChild(h);
            if (items.length === 0) {
                const p = document.createElement("p");
                p.className = "muted";
                p.textContent = "—";
                c.appendChild(p);
            } else {
                c.appendChild(makeBulletList(items));
            }
            return c;
        }

        wrap.appendChild(col("Functional", fn));
        wrap.appendChild(col("Non-functional", nfn));
        outer.appendChild(wrap);
        return outer;
    }

    function renderIntroCapacity(rows) {
        const outer = document.createElement("div");
        if (state.data && hasDiagram(state.data.capacityDiagram)) {
            // Capacity-estimation diagrams lay out left-to-right.
            outer.appendChild(makeMermaidEl(forceFlowchartDirection(state.data.capacityDiagram, "LR")));
        }
        const table = document.createElement("table");
        table.className = "capacity-table";
        const thead = document.createElement("thead");
        thead.innerHTML = "<tr><th>Metric</th><th>Estimate</th><th>Note</th></tr>";
        table.appendChild(thead);
        const tbody = document.createElement("tbody");
        for (const r of rows) {
            const tr = document.createElement("tr");
            const td1 = document.createElement("td");
            td1.textContent = r.label || "";
            const td2 = document.createElement("td");
            td2.className = "mono";
            td2.textContent = r.value || "";
            const td3 = document.createElement("td");
            td3.className = "muted";
            td3.textContent = r.note || "";
            tr.appendChild(td1);
            tr.appendChild(td2);
            tr.appendChild(td3);
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        outer.appendChild(table);
        return outer;
    }

    function renderIntroApi(rows) {
        const wrap = document.createElement("div");
        wrap.className = "api-list";
        for (const r of rows) {
            const card = document.createElement("div");
            card.className = "api-card";
            const head = document.createElement("div");
            head.className = "api-head";
            const method = document.createElement("span");
            method.className = `api-method method-${(r.method || "").toLowerCase()}`;
            method.textContent = r.method || "";
            const path = document.createElement("span");
            path.className = "api-path mono";
            path.textContent = r.path || "";
            head.appendChild(method);
            head.appendChild(path);
            card.appendChild(head);

            if (r.description) {
                const desc = document.createElement("p");
                desc.className = "api-desc";
                desc.textContent = r.description;
                card.appendChild(desc);
            }
            if (r.request) {
                const lbl = document.createElement("div");
                lbl.className = "api-label muted";
                lbl.textContent = "Request";
                const pre = document.createElement("pre");
                pre.className = "api-code";
                pre.textContent = r.request;
                card.appendChild(lbl);
                card.appendChild(pre);
            }
            if (r.response) {
                const lbl = document.createElement("div");
                lbl.className = "api-label muted";
                lbl.textContent = "Response";
                const pre = document.createElement("pre");
                pre.className = "api-code";
                pre.textContent = r.response;
                card.appendChild(lbl);
                card.appendChild(pre);
            }
            // Per-endpoint flow diagrams live in the dedicated "API Flows" section.
            wrap.appendChild(card);
        }
        return wrap;
    }

    // Wrap-up: API Flows. Renders one card per endpoint that has a `diagram`,
    // showing method+path and the sequence diagram only (contract details
    // remain on the Overview > API Design page).
    function renderIntroApiFlows(rows) {
        const wrap = document.createElement("div");
        wrap.className = "api-list";
        for (const r of rows) {
            const card = document.createElement("div");
            card.className = "api-card";

            const head = document.createElement("div");
            head.className = "api-head";
            const method = document.createElement("span");
            method.className = `api-method method-${(r.method || "").toLowerCase()}`;
            method.textContent = r.method || "";
            const path = document.createElement("span");
            path.className = "api-path mono";
            path.textContent = r.path || "";
            head.appendChild(method);
            head.appendChild(path);
            card.appendChild(head);

            if (r.description) {
                const desc = document.createElement("p");
                desc.className = "api-desc";
                desc.textContent = r.description;
                card.appendChild(desc);
            }

            if (hasDiagram(r.diagram)) {
                card.appendChild(makeMermaidEl(r.diagram, "api-diagram"));
            } else {
                const placeholder = document.createElement("p");
                placeholder.className = "muted api-flow-placeholder";
                placeholder.textContent = "No flow diagram defined for this endpoint.";
                card.appendChild(placeholder);
            }

            wrap.appendChild(card);
        }
        if (wrap.children.length === 0) {
            const p = document.createElement("p");
            p.className = "muted";
            p.textContent = "No API endpoints defined.";
            wrap.appendChild(p);
        }
        return wrap;
    }

    function renderIntroDataModel(tables) {
        const outer = document.createElement("div");

        const wrap = document.createElement("div");
        wrap.className = "schema-list";
        for (const t of tables) {
            const card = document.createElement("div");
            card.className = "schema-card";
            const h = document.createElement("h3");
            h.textContent = t.name || "table";
            card.appendChild(h);
            if (t.note) {
                const n = document.createElement("p");
                n.className = "muted schema-note";
                n.textContent = t.note;
                card.appendChild(n);
            }
            const tbl = document.createElement("table");
            tbl.className = "schema-table";
            const thead = document.createElement("thead");
            thead.innerHTML = "<tr><th>Field</th><th>Type</th><th>Note</th></tr>";
            tbl.appendChild(thead);
            const tbody = document.createElement("tbody");
            for (const f of t.fields || []) {
                const tr = document.createElement("tr");
                const td1 = document.createElement("td");
                td1.className = "mono";
                td1.textContent = f.name || "";
                const td2 = document.createElement("td");
                td2.className = "mono";
                td2.textContent = f.type || "";
                const td3 = document.createElement("td");
                td3.className = "muted";
                td3.textContent = f.note || "";
                tr.appendChild(td1);
                tr.appendChild(td2);
                tr.appendChild(td3);
                tbody.appendChild(tr);
            }
            tbl.appendChild(tbody);
            card.appendChild(tbl);
            wrap.appendChild(card);
        }
        outer.appendChild(wrap);

        let erSrc = null;
        if (state.data && hasDiagram(state.data.dataModelDiagram)) {
            erSrc = diagramSource(state.data.dataModelDiagram);
        } else {
            erSrc = autoErDiagramFromDataModel(tables);
        }
        if (erSrc) outer.appendChild(makeMermaidEl(erSrc, "er-diagram"));

        return outer;
    }

    // Step chips that navigate to a step entry on click.
    function makeStepChips(stepIds) {
        const wrap = document.createElement("div");
        wrap.className = "step-chips";
        for (const sid of stepIds || []) {
            const idx = state.entries.findIndex((e) => e.kind === "step" && e.id === sid);
            const chip = document.createElement(idx >= 0 ? "button" : "span");
            chip.className = "step-chip" + (idx >= 0 ? "" : " step-chip-missing");
            const stepEntry = idx >= 0 ? state.entries[idx] : null;
            chip.textContent = stepEntry ? stepEntry.title : sid;
            if (idx >= 0) {
                chip.type = "button";
                chip.addEventListener("click", () => selectEntry(idx));
            }
            wrap.appendChild(chip);
        }
        return wrap;
    }

    function renderIntroSatisfies(payload) {
        const wrap = document.createElement("div");
        wrap.className = "satisfies-columns";

        function col(title, items) {
            const c = document.createElement("div");
            c.className = "satisfies-col";
            const h = document.createElement("h3");
            h.textContent = title;
            c.appendChild(h);
            if (!items || items.length === 0) {
                const p = document.createElement("p");
                p.className = "muted";
                p.textContent = "—";
                c.appendChild(p);
                return c;
            }
            for (const it of items) {
                const card = document.createElement("div");
                card.className = "satisfies-card";

                const req = document.createElement("div");
                req.className = "satisfies-req";
                req.textContent = it.requirement || "";
                card.appendChild(req);

                if (it.how) {
                    const how = document.createElement("p");
                    how.className = "satisfies-how";
                    how.textContent = it.how;
                    card.appendChild(how);
                }

                if (Array.isArray(it.steps) && it.steps.length > 0) {
                    card.appendChild(makeStepChips(it.steps));
                }
                c.appendChild(card);
            }
            return c;
        }

        wrap.appendChild(col("Functional", payload.functional));
        wrap.appendChild(col("Non-functional", payload.nonFunctional));
        return wrap;
    }

    function renderIntroFollowUps(items) {
        const wrap = document.createElement("div");
        wrap.className = "followups-card";
        wrap.appendChild(makeBulletList(items));
        return wrap;
    }

    // Overview > Patterns. Each item: { name, what, whenToUse?, steps? }.
    // Names the reusable design patterns this case teaches and links them to
    // the steps where they appear.
    function renderIntroPatterns(items) {
        const wrap = document.createElement("div");
        wrap.className = "patterns-list";
        for (const p of items) {
            const card = document.createElement("div");
            card.className = "pattern-card";

            const name = document.createElement("div");
            name.className = "pattern-name";
            name.textContent = p.name || "";
            card.appendChild(name);

            if (p.what) {
                const what = document.createElement("p");
                what.className = "pattern-what";
                what.textContent = p.what;
                card.appendChild(what);
            }
            if (p.whenToUse) {
                const wt = document.createElement("p");
                wt.className = "pattern-when muted";
                wt.textContent = `When to use: ${p.whenToUse}`;
                card.appendChild(wt);
            }
            if (Array.isArray(p.steps) && p.steps.length > 0) {
                card.appendChild(makeStepChips(p.steps));
            }
            wrap.appendChild(card);
        }
        return wrap;
    }

    // Pattern Catalog (catalog dataset). Each item: { name, category?, what,
    // whenToUse?, tradeoffs?, usedBy? }. A standalone reference of the reusable
    // patterns the book teaches; cases reference these by name. Groups cards by
    // `category` when present.
    function renderIntroPatternCatalog(items) {
        const outer = document.createElement("div");

        // Group items by category (preserving first-seen order); ungrouped last.
        const order = [];
        const byCat = new Map();
        for (const p of items) {
            const cat = p.category || "";
            if (!byCat.has(cat)) {
                byCat.set(cat, []);
                order.push(cat);
            }
            byCat.get(cat).push(p);
        }

        for (const cat of order) {
            if (cat) {
                const h = document.createElement("h3");
                h.className = "catalog-category";
                h.textContent = cat;
                outer.appendChild(h);
            }
            const grid = document.createElement("div");
            grid.className = "patterns-list";
            for (const p of byCat.get(cat)) {
                const card = document.createElement("div");
                card.className = "pattern-card";

                const name = document.createElement("div");
                name.className = "pattern-name";
                name.textContent = p.name || "";
                card.appendChild(name);

                if (p.what) {
                    const what = document.createElement("p");
                    what.className = "pattern-what";
                    what.textContent = p.what;
                    card.appendChild(what);
                }
                if (p.whenToUse) {
                    const wt = document.createElement("p");
                    wt.className = "pattern-when muted";
                    wt.textContent = `When to use: ${p.whenToUse}`;
                    card.appendChild(wt);
                }
                if (p.tradeoffs) {
                    const tr = document.createElement("p");
                    tr.className = "pattern-tradeoffs";
                    tr.textContent = `Trade-off: ${p.tradeoffs}`;
                    card.appendChild(tr);
                }
                if (Array.isArray(p.usedBy) && p.usedBy.length > 0) {
                    const used = document.createElement("div");
                    used.className = "pattern-tags";
                    for (const u of p.usedBy) {
                        const chip = document.createElement("span");
                        chip.className = "pattern-tag";
                        chip.textContent = String(u);
                        used.appendChild(chip);
                    }
                    card.appendChild(used);
                }
                grid.appendChild(card);
            }
            outer.appendChild(grid);
        }
        return outer;
    }

    // Wrap-up > Interview Script. Each item: { phase, time?, say }.
    // What to say across the interview's phases (first 5 min, 15, 30, final 5).
    function renderIntroInterviewScript(items) {
        const wrap = document.createElement("div");
        wrap.className = "script-timeline";
        for (const s of items) {
            const card = document.createElement("div");
            card.className = "script-phase";

            const head = document.createElement("div");
            head.className = "script-head";
            const phase = document.createElement("span");
            phase.className = "script-phase-name";
            phase.textContent = s.phase || "";
            head.appendChild(phase);
            if (s.time) {
                const time = document.createElement("span");
                time.className = "script-time mono";
                time.textContent = s.time;
                head.appendChild(time);
            }
            card.appendChild(head);
            card.appendChild(makeBulletList(bulletsFrom(s.say || [])));
            wrap.appendChild(card);
        }
        return wrap;
    }

    // Wrap-up > By Level. Each item: { level, expectations }.
    // Junior / senior / staff expectations side by side.
    function renderIntroLevelVariants(items) {
        const wrap = document.createElement("div");
        wrap.className = "level-columns";
        for (const lv of items) {
            const col = document.createElement("div");
            col.className = "level-col";
            const h = document.createElement("h3");
            h.textContent = lv.level || "";
            col.appendChild(h);
            col.appendChild(makeBulletList(bulletsFrom(lv.expectations || [])));
            wrap.appendChild(col);
        }
        return wrap;
    }

    function renderIntroEntry(entry) {
        els.introBlock.innerHTML = "";
        let node;
        switch (entry.id) {
            case INTRO_SLUGS.requirements:
                node = renderIntroRequirements(entry.payload);
                break;
            case INTRO_SLUGS.capacity:
                node = renderIntroCapacity(entry.payload);
                break;
            case INTRO_SLUGS.api:
                node = renderIntroApi(entry.payload);
                break;
            case INTRO_SLUGS.dataModel:
                node = renderIntroDataModel(entry.payload);
                break;
            case INTRO_SLUGS.apiFlows:
                node = renderIntroApiFlows(entry.payload);
                break;
            case INTRO_SLUGS.patterns:
                node = renderIntroPatterns(entry.payload);
                break;
            case INTRO_SLUGS.patternCatalog:
                node = renderIntroPatternCatalog(entry.payload);
                break;
            case INTRO_SLUGS.satisfies:
                node = renderIntroSatisfies(entry.payload);
                break;
            case INTRO_SLUGS.interviewScript:
                node = renderIntroInterviewScript(entry.payload);
                break;
            case INTRO_SLUGS.levelVariants:
                node = renderIntroLevelVariants(entry.payload);
                break;
            case INTRO_SLUGS.followUps:
                node = renderIntroFollowUps(entry.payload);
                break;
            default:
                node = document.createElement("div");
                node.textContent = "(no renderer for this section)";
        }
        els.introBlock.appendChild(node);
    }

    // ---------- Top-level render ----------

    function previousStepBefore(entryIndex) {
        for (let i = entryIndex - 1; i >= 0; i--) {
            if (state.entries[i].kind === "step") return state.entries[i].payload;
        }
        return null;
    }

    async function renderStepLikeEntry(entry, prevStep) {
        const step = entry.payload;
        renderDescription(step.description, step.decisionPrompt, step.concepts);

        if (Array.isArray(step.options) && step.options.length > 0) {
            if (state.currentOptionIndex >= step.options.length) state.currentOptionIndex = 0;
        } else {
            state.currentOptionIndex = 0;
        }

        els.introBlock.hidden = true;
        els.diagramBlock.hidden = false;
        renderDiagramViewTabs(entry);
        renderOptionTabs(step);
        renderProsCons(step);
        const focus = effectiveDiagramFor(step);
        let diagram = focus.diagram;
        let highlight = focus.highlight;
        let diagramPrevStep = prevStep;
        if (entry.kind === "step" && state.currentDiagramView === "context") {
            highlight = resolveHighlights(
                {diagram: focus.diagram, highlight: focus.highlight},
                defaultEffectiveFor(prevStep)
            );
            diagram = fullContextDiagramFor(state.currentEntryIndex, focus.diagram);
            diagramPrevStep = null;
        }
        await renderDiagram(diagram, highlight, diagramPrevStep);

        renderStepExtras(step);
    }

    async function renderCurrentEntry() {
        const entry = state.entries[state.currentEntryIndex];
        if (!entry) return;

        updateNavActive();
        els.stepTitle.textContent = entry.title || "";
        els.stepCounter.textContent = `${state.currentEntryIndex + 1} / ${state.entries.length}`;
        els.prevBtn.disabled = state.currentEntryIndex === 0;
        els.nextBtn.disabled = state.currentEntryIndex === state.entries.length - 1;

        if (entry.id === INTRO_SLUGS.finalDesign) {
            await renderStepLikeEntry(entry, null);
        } else if (entry.kind === "intro") {
            els.stepDescription.innerHTML = "";
            els.diagramBlock.hidden = true;
            els.stepExtras.innerHTML = "";
            els.introBlock.hidden = false;
            renderIntroEntry(entry);
        } else {
            await renderStepLikeEntry(entry, previousStepBefore(state.currentEntryIndex));
        }

        updateHash();
    }

    // ---------- Navigation ----------

    function selectEntry(index) {
        const clamped = Math.max(0, Math.min(index, state.entries.length - 1));
        if (clamped === state.currentEntryIndex) return;
        state.currentEntryIndex = clamped;
        state.currentOptionIndex = 0; // reset on entry change
        state.currentFlowIndex = 0;
        state.currentDiagramView = "focus";
        renderCurrentEntry();
    }

    function selectDiagramView(view) {
        const entry = state.entries[state.currentEntryIndex];
        if (!entry || entry.kind !== "step") return;
        if (view !== "focus" && view !== "context") return;
        if (view === state.currentDiagramView) return;
        state.currentDiagramView = view;
        renderCurrentEntry();
    }

    function selectFlow(index) {
        const entry = state.entries[state.currentEntryIndex];
        if (!entry || (entry.kind !== "step" && entry.id !== INTRO_SLUGS.finalDesign)) return;
        const flows = Array.isArray(entry.payload.flows) ? entry.payload.flows : [];
        const validCount = flows.filter(
            (f) => f && hasDiagram(f.diagram)
        ).length;
        if (validCount === 0) return;
        const clamped = Math.max(0, Math.min(index, validCount - 1));
        if (clamped === state.currentFlowIndex) return;
        state.currentFlowIndex = clamped;
        renderCurrentEntry();
    }

    function selectOption(index) {
        const entry = state.entries[state.currentEntryIndex];
        if (!entry || (entry.kind !== "step" && entry.id !== INTRO_SLUGS.finalDesign)) return;
        const opts = entry.payload.options;
        if (!Array.isArray(opts)) return;
        const clamped = Math.max(0, Math.min(index, opts.length - 1));
        if (clamped === state.currentOptionIndex) return;
        state.currentOptionIndex = clamped;
        renderCurrentEntry();
    }

    function updateHash() {
        const entry = state.entries[state.currentEntryIndex];
        const id = entry && entry.id ? entry.id : String(state.currentEntryIndex + 1);
        const newHash = `#${state.currentDatasetId}/${id}`;
        if (location.hash !== newHash) history.replaceState(null, "", newHash);
    }

    function parseHash() {
        const h = location.hash.replace(/^#/, "");
        if (!h) return null;
        const [datasetId, entryId] = h.split("/");
        return {datasetId: datasetId || null, entryId: entryId || null};
    }

    // ---------- Dataset loading ----------

    function validateDataset(d, path) {
        if (!d || typeof d !== "object") throw new Error(`Dataset ${path}: not an object`);
        const hasSteps = Array.isArray(d.steps) && d.steps.length > 0;
        const hasCatalog = Array.isArray(d.patternCatalog) && d.patternCatalog.length > 0;
        // A normal interview needs steps[]. A catalog dataset (no system to walk
        // through) is valid with a non-empty patternCatalog[] instead.
        if (!hasSteps && !hasCatalog) {
            throw new Error(`Dataset ${path}: needs a non-empty "steps" array (or a "patternCatalog" for a catalog dataset)`);
        }
        (d.steps || []).forEach((step, i) => {
            if (!step || typeof step !== "object") throw new Error(`Step ${i} is not an object`);
            if (!hasStepLikeDiagram(step)) {
                throw new Error(`Step ${i} ("${step.title || step.id || ""}") must define a "diagram" or non-empty "options[].diagram"`);
            }
        });
        if (d.finalDesign && !hasStepLikeDiagram(d.finalDesign)) {
            throw new Error(`Dataset ${path}: "finalDesign" must define a "diagram" or non-empty "options[].diagram"`);
        }
        // Book-feature fields are optional, but if present must be arrays so the
        // renderers can iterate them. Contents stay free-form (rendered only if
        // present), matching the rest of the lenient schema.
        for (const key of ["patterns", "interviewScript", "levelVariants", "patternCatalog"]) {
            if (d[key] !== undefined && !Array.isArray(d[key])) {
                throw new Error(`Dataset ${path}: "${key}" must be an array if present`);
            }
        }
        (d.steps || []).forEach((step, i) => {
            for (const key of ["patterns", "traps"]) {
                if (step[key] !== undefined && !Array.isArray(step[key])) {
                    throw new Error(`Step ${i} ("${step.title || step.id || ""}"): "${key}" must be an array if present`);
                }
            }
        });
    }

    async function loadDataset(datasetId, initialEntryId) {
        const meta = state.datasets.find((d) => d.id === datasetId);
        if (!meta) {
            showError(`Unknown dataset: ${datasetId}`);
            return;
        }
        try {
            const data = await fetchJson(meta.path);
            validateDataset(data, meta.path);
            state.currentDatasetId = datasetId;
            state.data = data;
            state.entries = buildEntries(data);

            els.datasetTitle.textContent = data.title || meta.name || "System Design Explorer";
            els.datasetDescription.textContent = data.description || "";

            let startIndex = 0;
            if (initialEntryId) {
                const idx = state.entries.findIndex((e) => e.id === initialEntryId);
                if (idx >= 0) startIndex = idx;
            }
            state.currentEntryIndex = startIndex;
            state.currentOptionIndex = 0;
            state.currentFlowIndex = 0;
            state.currentDiagramView = "focus";

            renderNav();
            await renderCurrentEntry();
        } catch (err) {
            showError(err.message || String(err));
        }
    }

    // Accepts both the grouped manifest ({ groups: [{ id, name, datasets }] })
    // and the legacy flat manifest ({ datasets: [...] }). Returns
    // { groups, datasets } where `datasets` is the flat list and each dataset
    // carries its resolved `group` / `groupName`.
    function normalizeManifest(manifest) {
        if (manifest && Array.isArray(manifest.groups)) {
            const groups = manifest.groups
                .filter((g) => g && Array.isArray(g.datasets))
                .map((g) => ({
                    id: g.id || g.name || "group",
                    name: g.name || g.id || "Group",
                    datasets: g.datasets,
                }));
            const datasets = [];
            groups.forEach((g) => {
                g.datasets.forEach((d) => {
                    datasets.push(Object.assign({groupId: g.id, groupName: g.name}, d));
                });
            });
            return {groups, datasets};
        }
        if (manifest && Array.isArray(manifest.datasets)) {
            const datasets = manifest.datasets.slice();
            return {groups: [{id: "all", name: "Interviews", datasets}], datasets};
        }
        return {groups: [], datasets: []};
    }

    function populateDatasetSelect() {
        els.datasetSelect.innerHTML = "";
        const single = state.groups.length <= 1;
        state.groups.forEach((g) => {
            const parent = single
                ? els.datasetSelect
                : els.datasetSelect.appendChild(
                      Object.assign(document.createElement("optgroup"), {label: g.name})
                  );
            g.datasets.forEach((d) => {
                const opt = document.createElement("option");
                opt.value = d.id;
                opt.textContent = d.name || d.id;
                parent.appendChild(opt);
            });
        });
    }

    async function init() {
        try {
            const manifest = await fetchJson("data/index.json");
            const {groups, datasets} = normalizeManifest(manifest);
            if (datasets.length === 0) {
                throw new Error('data/index.json must contain a non-empty "groups" or "datasets" array');
            }
            state.groups = groups;
            state.datasets = datasets;
            populateDatasetSelect();

            const hash = parseHash();
            const initialDatasetId = (hash && hash.datasetId && state.datasets.find((d) => d.id === hash.datasetId))
                ? hash.datasetId
                : state.datasets[0].id;
            const initialEntryId = hash ? hash.entryId : null;

            els.datasetSelect.value = initialDatasetId;
            await loadDataset(initialDatasetId, initialEntryId);
        } catch (err) {
            showError(err.message || String(err));
        }
    }

    // ---------- Event wiring ----------

    els.prevBtn.addEventListener("click", () => selectEntry(state.currentEntryIndex - 1));
    els.nextBtn.addEventListener("click", () => selectEntry(state.currentEntryIndex + 1));

    els.datasetSelect.addEventListener("change", (e) => loadDataset(e.target.value, null));

    document.addEventListener("keydown", (e) => {
        const t = e.target;
        if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
        if (e.key === "ArrowLeft") {
            e.preventDefault();
            selectEntry(state.currentEntryIndex - 1);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            selectEntry(state.currentEntryIndex + 1);
        }
    });

    window.addEventListener("hashchange", () => {
        const h = parseHash();
        if (!h) return;
        if (h.datasetId && h.datasetId !== state.currentDatasetId) {
            els.datasetSelect.value = h.datasetId;
            loadDataset(h.datasetId, h.entryId);
            return;
        }
        if (h.entryId && state.entries.length > 0) {
            const idx = state.entries.findIndex((e) => e.id === h.entryId);
            if (idx >= 0) selectEntry(idx);
        }
    });

    init();
})();
