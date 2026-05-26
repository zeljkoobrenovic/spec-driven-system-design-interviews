// System Design Step-by-Step Explorer
// Vanilla JS, no build step. Loads a manifest of datasets, then a per-dataset
// JSON file containing both dataset-level interview sections (requirements,
// capacity, API, data model, follow-ups) and a sequence of architecture
// steps with structured graph views.

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
        diagramLegend: document.getElementById("diagram-legend"),
        optionTabs: document.getElementById("option-tabs"),
        optionDescription: document.getElementById("option-description"),
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
        currentDatasetPath: null,
        data: null,
        nodeTypeConfig: null,
        nodeIndex: null,
        linkIndex: null,
        architectureTypeIndex: null,
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
        concepts: "concepts",
        patternCatalog: "pattern-catalog",
        finalDesign: "final-design",
        apiFlows: "api-flows",
        satisfies: "satisfies",
        interviewScript: "interview-script",
        levelVariants: "by-level",
        followUps: "follow-ups",
        toProbeFurther: "to-probe-further",
    };

    // Slugs that belong in the bottom "Wrap-up" sidebar group, in order.
    const WRAPUP_ORDER = [
        INTRO_SLUGS.apiFlows,
        INTRO_SLUGS.satisfies,
        INTRO_SLUGS.levelVariants,
        INTRO_SLUGS.followUps,
        INTRO_SLUGS.toProbeFurther,
    ];
    const WRAPUP_SLUGS = new Set(WRAPUP_ORDER);
    const ARCHITECTURE_INTRO_SLUGS = new Set([INTRO_SLUGS.finalDesign]);

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

    function assetUrl(path) {
        if (!path || typeof path !== "string") return "";
        if (/^(?:https?:|data:|\/)/.test(path)) return path;
        const basePath = state.currentDatasetPath || "";
        const base = basePath.includes("/") ? basePath.replace(/\/[^/]*$/, "/") : "";
        return base + path.replace(/^\.\//, "");
    }

    // Shared fallback icons (site-root-relative, alongside index.html). Used
    // when a concept/pattern has no per-item icon, or its icon fails to load.
    const ICON_FALLBACK = {
        concept: "icons/concept.png",
        pattern: "icons/pattern.png",
        trap: "icons/trap.png",
        before: "icons/before.png",
        after: "icons/after.png",
        risk: "icons/risk.png",
        failureDrill: "icons/failure-drill.png",
        deepDive: "icons/deep-dive.png",
        talkingPoints: "icons/talking-points.png",
        mitigations: "icons/mitigations.png",
        designMove: "icons/design-move.png",
        whyNow: "icons/why-now.png",
        decisionPoint: "icons/decision-point.png",
    };

    // `fallback` is a site-root-relative path (e.g. ICON_FALLBACK.concept) used
    // when `path` is absent or fails to load. With a fallback, an icon is
    // always shown; without one, a missing/broken icon yields null / is removed.
    function makeAssetIcon(path, alt, fallback) {
        const src = assetUrl(path) || (fallback || "");
        if (!src) return null;
        const img = document.createElement("img");
        img.className = "asset-icon";
        img.src = src;
        img.alt = alt || "";
        img.loading = "lazy";
        img.decoding = "async";
        img.addEventListener("error", function onErr() {
            if (fallback && !img.src.endsWith(fallback)) {
                img.src = fallback; // dataset icon missing -> shared fallback
                return;
            }
            img.removeEventListener("error", onErr);
            img.remove();
        });
        return img;
    }

    function renderGeneratedImage(path, alt) {
        const src = assetUrl(path);
        if (!src) return null;
        const figure = document.createElement("figure");
        figure.className = "generated-image-card";
        const link = document.createElement("a");
        link.className = "generated-image-link";
        link.href = src;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        const img = document.createElement("img");
        img.className = "generated-image";
        img.src = src;
        img.alt = alt || "Generated image";
        img.loading = "lazy";
        img.decoding = "async";
        link.appendChild(img);
        figure.appendChild(link);
        const section = makeSection("Generated Image", figure, "generated-image-section");
        img.addEventListener("error", () => {
            section.remove();
        });
        return section;
    }

    async function loadNodeTypeConfig() {
        const cfg = await fetchJson("node-types.json");
        return cfg && typeof cfg === "object" ? cfg : {};
    }

    function diagramSource(value) {
        if (Array.isArray(value)) return value.join("\n");
        return typeof value === "string" ? value : "";
    }

    function hasDiagram(value) {
        return diagramSource(value).trim() !== "";
    }

    function hasGraphView(value) {
        return !!(value && typeof value === "object" && (
            Array.isArray(value.nodes) ||
            Array.isArray(value.links) ||
            Array.isArray(value.groups)
        ));
    }

    function hasSequence(value) {
        return !!(value && typeof value === "object" &&
            Array.isArray(value.participants) &&
            Array.isArray(value.messages));
    }

    function hasStepLikeDiagram(item) {
        if (!item || typeof item !== "object") return false;
        const hasOwn = hasGraphView(item.view);
        const hasOpt = Array.isArray(item.options) && item.options.length > 0 &&
            item.options.every((o) => o && hasGraphView(o.view));
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
            "classDef newNode stroke:crimson,stroke-width:3.6px;\n" +
            `class ${safe.join(",")} newNode;`;
    }

    function escapeHtmlLabel(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function decodeMermaidLabel(text) {
        return String(text || "")
            .replace(/&quot;/g, "\"")
            .replace(/&amp;/g, "&")
            .replace(/#38;/g, "&")
            .replace(/#40;/g, "(")
            .replace(/#41;/g, ")")
            .replace(/#91;/g, "[")
            .replace(/#93;/g, "]")
            .replace(/#123;/g, "{")
            .replace(/#125;/g, "}")
            .replace(/#124;/g, "|");
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

    const NODE_TYPE_CATEGORIES = {
        actor: "boundary",
        client: "boundary",
        edge: "boundary",
        gateway: "traffic",
        service: "compute",
        orchestrator: "compute",
        worker: "compute",
        queue: "async",
        stream: "async",
        cache: "state",
        database: "state",
        "object-storage": "state",
        index: "state",
        model: "compute",
        observability: "ops",
        external: "boundary",
    };

    function canonicalNodeType(type) {
        const t = String(type || "").trim().toLowerCase();
        return NODE_TYPE_CATEGORIES[t] ? t : "";
    }

    function nodeTypeCategory(type) {
        return NODE_TYPE_CATEGORIES[canonicalNodeType(type)] || "";
    }

    function normalizeNodeLookupLabel(label) {
        return String(label || "")
            .replace(/\\n/g, "\n")
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/\s+/g, " ")
            .trim();
    }

    function nodeLookupKey(id, label) {
        return `${String(id || "")}\u0000${normalizeNodeLookupLabel(label)}`;
    }

    function normalizeNodeMeta(item) {
        if (!item || typeof item !== "object") return null;
        const id = String(item.id || "").trim();
        const type = canonicalNodeType(item.type);
        if (!id || !type) return null;
        const label = normalizeNodeLookupLabel(item.label || id);
        return {
            id,
            label,
            type,
            category: String(item.category || nodeTypeCategory(type) || "").trim(),
            traits: Array.isArray(item.traits)
                ? item.traits.map((t) => String(t || "").trim()).filter(Boolean)
                : [],
            description: String(item.description || "").trim(),
        };
    }

    function buildNodeIndex(data) {
        const exact = new Map();
        const byId = new Map();
        const arch = data && data.highLevelArchitecture;
        const items = arch && Array.isArray(arch.nodes) ? arch.nodes : [];

        items.forEach((item) => {
            const meta = normalizeNodeMeta(item);
            if (!meta) return;
            exact.set(nodeLookupKey(meta.id, meta.label), meta);
            if (!byId.has(meta.id)) byId.set(meta.id, []);
            byId.get(meta.id).push(meta);
        });

        return {exact, byId};
    }

    function nodeMetadataFor(id, label) {
        if (!state.nodeIndex || !id) return null;
        const exact = state.nodeIndex.exact.get(nodeLookupKey(id, label));
        if (exact) return exact;

        const matches = state.nodeIndex.byId.get(String(id || "").trim()) || [];
        if (matches.length === 1) return matches[0];

        const normalizedLabel = normalizeNodeLookupLabel(label);
        const sameLabel = matches.filter((m) => m.label === normalizedLabel);
        return sameLabel.length === 1 ? sameLabel[0] : null;
    }

    function normalizeNodeRef(ref) {
        if (typeof ref === "string") return {id: ref};
        if (ref && typeof ref === "object") {
            return {
                id: String(ref.id || "").trim(),
                label: ref.label !== undefined ? normalizeNodeLookupLabel(ref.label) : undefined,
                render: ref.render && typeof ref.render === "object" ? ref.render : null,
            };
        }
        return {id: ""};
    }

    function nodeMetadataForRef(ref) {
        const r = normalizeNodeRef(ref);
        if (!r.id) return null;
        return nodeMetadataFor(r.id, r.label || "") || {
            id: r.id,
            label: r.label || r.id,
            type: "",
            category: "",
            traits: [],
            description: "",
        };
    }

    function buildLinkIndex(data) {
        const out = new Map();
        const arch = data && data.highLevelArchitecture;
        const items = arch && Array.isArray(arch.links) ? arch.links : [];
        items.forEach((link) => {
            if (!link || typeof link !== "object") return;
            const id = String(link.id || "").trim();
            if (!id) return;
            out.set(id, Object.assign({}, link, {id}));
        });
        return out;
    }

    function buildArchitectureTypeIndex(data) {
        const out = new Map();
        const arch = data && data.highLevelArchitecture;
        const items = arch && Array.isArray(arch.types) ? arch.types : [];
        items.forEach((group) => {
            if (!group || typeof group !== "object") return;
            const id = String(group.id || "").trim();
            if (!id) return;
            out.set(id, Object.assign({}, group, {id}));
        });
        return out;
    }

    function nodeRenderingConfig() {
        return state.nodeTypeConfig && state.nodeTypeConfig.rendering && typeof state.nodeTypeConfig.rendering === "object"
            ? state.nodeTypeConfig.rendering
            : {};
    }

    function safeMermaidClassName(value, fallback) {
        const raw = String(value || fallback || "").trim();
        const safe = raw.replace(/[^A-Za-z0-9_-]/g, "_");
        if (/^[A-Za-z_]/.test(safe)) return safe || "nodeType";
        return `nodeType_${safe}`;
    }

    function nodeTypeStyle(type) {
        const canonical = canonicalNodeType(type);
        if (!canonical) return null;
        const config = nodeRenderingConfig();
        const defaults = config.defaults && typeof config.defaults === "object" ? config.defaults : {};
        const types = config.types && typeof config.types === "object" ? config.types : {};
        const spec = types[canonical] && typeof types[canonical] === "object" ? types[canonical] : {};
        const className = safeMermaidClassName(spec.className, canonical);
        return {
            type: canonical,
            className,
            shape: String(spec.shape || defaults.shape || "rect"),
            fill: String(spec.fill || defaults.fill || "#ffffff"),
            stroke: String(spec.stroke || defaults.stroke || "#d1d5db"),
            strokeWidth: String(spec.strokeWidth || defaults.strokeWidth || "1.4px"),
            color: String(spec.color || defaults.color || "#1f2329"),
            captionColor: String(spec.captionColor || spec.stroke || defaults.captionColor || "#6a7280"),
        };
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
        const canonicalType = canonicalNodeType(type);
        const style = nodeTypeStyle(type);
        const renderShape = style ? style.shape : "";
        const captionColor = style ? style.captionColor : "#6a7280";
        const topSpacer = renderShape === "database"
            ? "<span class='node-label-top-spacer' style='display:block;height:1em;line-height:1em;'>&nbsp;</span>"
            : "";
        const caption = canonicalType
            ? `<span class='node-type-caption' style='display:block;margin:0 0 1px;color:${escapeHtmlLabel(captionColor)};font-size:10px;line-height:1;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;'>${escapeHtmlLabel(canonicalType)}</span>`
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
            {shape: "rect", re: /^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\[(.+)\](\s*)$/}
        ];

        const typeClasses = new Map();

        function rememberTypeClass(id, type) {
            const style = nodeTypeStyle(type);
            if (!style) return;
            if (!typeClasses.has(style.className)) typeClasses.set(style.className, {style, ids: []});
            typeClasses.get(style.className).ids.push(id);
        }

        function rebuild(shape, id, label) {
            const decodedLabel = decodeMermaidLabel(label);
            const meta = nodeMetadataFor(id, decodedLabel);
            const type = meta ? meta.type : "";
            if (/node-type-caption/.test(label)) return null;
            // Rebuild when the node has a known type OR carries an inline annotation
            // (a `\n` in the label), so annotation styling reaches typeless nodes too.
            const hasAnnotation = /\\n/.test(decodedLabel);
            if (!type && !hasAnnotation) return null;
            if (type) rememberTypeClass(id, type);
            const annotated = typeAnnotatedLabel(type, decodedLabel);
            const typeStyle = nodeTypeStyle(type);
            const renderedShape = typeStyle && typeStyle.shape ? typeStyle.shape : shape;
            // The annotated label is an HTML <span> (parens, semicolons, angle
            // brackets, slashes). Mermaid only accepts an HTML node label when it
            // is double-quoted inside the shape brackets; unquoted, the parser
            // breaks on the first ( / ; / etc. The span uses only single-quoted
            // attributes, so wrapping in " is safe (escape any stray " defensively).
            const q = `"${String(annotated).replace(/"/g, "&quot;")}"`;
            switch (renderedShape) {
                case "subroutine":
                    return `${id}[[${q}]]`;
                case "database":
                    return `${id}[(${q})]`;
                case "stadium":
                    return `${id}([${q}])`;
                case "circle":
                    return `${id}((${q}))`;
                case "diamond":
                    return `${id}{${q}}`;
                case "parallelogram":
                    return `${id}[/${q}/]`;
                case "asymmetric":
                    return `${id}>${q}]`;
                default:
                    return `${id}[${q}]`;
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
            classLines.push(`classDef ${className} fill:${style.fill},stroke:${style.stroke},stroke-width:${style.strokeWidth},color:${style.color};`);
            classLines.push(`class ${uniqueIds.join(",")} ${className};`);
        });

        return annotatedLines.concat(classLines).join("\n");
    }

    // Resolve which participants in `flow` should be highlighted at `currentStep`.
    // Strategy:
    //   - If flow.highlight is an explicit array, use it (filtered to known IDs).
    //   - Otherwise union:
    //       a) participants new to this step (not present in any earlier step's flows), and
    //       b) participants whose ID matches a node highlighted in the step view.
    function flowParticipantIds(flow) {
        const ids = new Set();
        if (!flow || !hasSequence(flow.sequence)) return ids;
        sequenceParticipantSpecs(flow.sequence).specs.forEach((spec) => {
            ids.add(spec.id);
            ids.add(spec.alias);
        });
        return ids;
    }

    function resolveFlowHighlights(flow, currentStep, allStepsBefore) {
        const flowParticipants = flowParticipantIds(flow);
        const explicitHighlight = Array.isArray(flow.highlight) && flow.highlight.length > 0
            ? flow.highlight
            : (flow.sequence && Array.isArray(flow.sequence.highlight) ? flow.sequence.highlight : []);

        if (explicitHighlight.length > 0) {
            // Only keep IDs that actually appear in the flow, so a typo or stale
            // reference doesn't inject orphan `class` lines.
            return explicitHighlight.filter((id) => flowParticipants.has(id));
        }

        const out = new Set();

        // (a) Diff against the union of all previous steps' flow participants.
        const seenBefore = new Set();
        for (const prev of allStepsBefore) {
            const flows = Array.isArray(prev.flows) ? prev.flows : [];
            for (const f of flows) {
                if (!hasFlowDiagram(f)) continue;
                for (const id of flowParticipantIds(f)) seenBefore.add(id);
            }
        }
        for (const id of flowParticipants) {
            if (!seenBefore.has(id)) out.add(id);
        }

        // (b) Inherit step view highlights that appear as participants here.
        const stepHighlight = currentStep.view && Array.isArray(currentStep.view.highlight)
            ? currentStep.view.highlight
            : [];
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

    function probeFurtherLinks(payload) {
        if (!payload) return [];
        if (Array.isArray(payload)) {
            if (payload.some((item) => item && typeof item === "object" && Array.isArray(item.links))) {
                const out = [];
                for (const group of payload) {
                    if (!group || typeof group !== "object" || !Array.isArray(group.links)) continue;
                    for (const link of group.links) {
                        if (!link || typeof link !== "object") continue;
                        out.push(Object.assign({
                            group: group.group || group.title || "",
                            groupDescription: group.description || "",
                        }, link));
                    }
                }
                return out;
            }
            return payload.filter((item) => item && typeof item === "object");
        }
        if (payload && typeof payload === "object" && Array.isArray(payload.links)) {
            return payload.links.filter((item) => item && typeof item === "object");
        }
        return [];
    }

    function probeFurtherGroups(payload, linksOverride) {
        const links = linksOverride || probeFurtherLinks(payload);
        const groupDefs = payload && typeof payload === "object" && !Array.isArray(payload) && Array.isArray(payload.groups)
            ? payload.groups
            : [];
        const order = [];
        const byGroup = new Map();

        for (const group of groupDefs) {
            if (!group || typeof group !== "object") continue;
            const name = group.group || group.title || group.id || "Further reading";
            if (!byGroup.has(name)) {
                byGroup.set(name, {
                    group: name,
                    description: group.description || "",
                    links: [],
                });
                order.push(name);
            }
        }

        for (const link of links) {
            const name = link.group || "Further reading";
            if (!byGroup.has(name)) {
                byGroup.set(name, {
                    group: name,
                    description: link.groupDescription || "",
                    links: [],
                });
                order.push(name);
            }
            const group = byGroup.get(name);
            if (!group.description && link.groupDescription) group.description = link.groupDescription;
            group.links.push(link);
        }

        return order.map((name) => byGroup.get(name)).filter((group) => group.links.length > 0);
    }

    function probeFurtherLinkIndex() {
        const index = new Map();
        for (const link of probeFurtherLinks(state.data && state.data.toProbeFurther)) {
            const id = String(link.id || "").trim();
            if (id && !index.has(id)) index.set(id, link);
        }
        return index;
    }

    function conceptKey(concept) {
        const raw = typeof concept === "string"
            ? concept
            : concept && (concept.term || concept.name || concept.title || concept.definition || concept.description);
        return String(raw || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, " ")
            .trim();
    }

    function cleanStepGroupTitle(step) {
        const raw = step && (step.title || step.id);
        return String(raw || "Design Step")
            .replace(/^\s*\d+[a-z]?\s*[\.)-]\s*/i, "")
            .replace(/\s+/g, " ")
            .trim() || "Design Step";
    }

    function collectDatasetConcepts(data) {
        const out = new Map();
        for (const step of data && Array.isArray(data.steps) ? data.steps : []) {
            const concepts = Array.isArray(step.concepts) ? step.concepts : [];
            const stepGroup = cleanStepGroupTitle(step);
            for (const concept of concepts) {
                const key = conceptKey(concept);
                if (!key) continue;

                const source = typeof concept === "string" ? {term: concept} : Object.assign({}, concept);
                if (!source.group) source.group = stepGroup;
                if (!out.has(key)) {
                    source.steps = Array.isArray(source.steps) ? source.steps.slice() : [];
                    out.set(key, source);
                }

                const target = out.get(key);
                if (!target.group && source.group) target.group = source.group;
                if (step.id && !target.steps.includes(step.id)) target.steps.push(step.id);
            }
        }
        return Array.from(out.values());
    }

    function introItemGroupName(item, fallback) {
        if (item && typeof item === "object") {
            const value = item.group || item.category;
            if (String(value || "").trim()) return String(value).trim();
        }
        return fallback || "Other";
    }

    function groupedIntroItems(items, fallback) {
        const order = [];
        const byGroup = new Map();
        for (const item of Array.isArray(items) ? items : []) {
            const name = introItemGroupName(item, fallback);
            if (!byGroup.has(name)) {
                byGroup.set(name, {name, items: []});
                order.push(name);
            }
            byGroup.get(name).items.push(item);
        }
        return order.map((name) => byGroup.get(name)).filter((group) => group.items.length > 0);
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
        const conceptItems = collectDatasetConcepts(data);
        if (conceptItems.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.concepts, title: "Concepts", payload: conceptItems});
        }
        if (Array.isArray(data.patternCatalog) && data.patternCatalog.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.patternCatalog, title: "Pattern Catalog", payload: data.patternCatalog});
        }
        if (Array.isArray(data.interviewScript) && data.interviewScript.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.interviewScript, title: "Interview Script", payload: data.interviewScript});
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
        if (Array.isArray(data.steps)) {
            for (const step of data.steps) entries.push({kind: "step", id: step.id, title: step.title, payload: step});
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
        if (Array.isArray(data.levelVariants) && data.levelVariants.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.levelVariants, title: "Expectations By Level", payload: data.levelVariants});
        }
        if (Array.isArray(data.followUps) && data.followUps.length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.followUps, title: "Follow-up Questions", payload: data.followUps});
        }
        if (probeFurtherLinks(data.toProbeFurther).length > 0) {
            entries.push({kind: "intro", id: INTRO_SLUGS.toProbeFurther, title: "To Probe Further", payload: data.toProbeFurther});
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
        const architectureEntries = state.entries.filter((e) => e.kind === "step" || ARCHITECTURE_INTRO_SLUGS.has(e.id));

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

        makeGroup("Overview", introEntries.filter((e) => !WRAPUP_SLUGS.has(e.id) && !ARCHITECTURE_INTRO_SLUGS.has(e.id)));
        makeGroup("High-Level Architecture", architectureEntries);
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

    // `icon` is an optional site-root fallback path; when set, the section's
    // <h3> title is shown alongside that icon (same .asset-heading treatment).
    function renderStepTextSection(title, value, className, icon) {
        const content = renderTextOrBullets(value, "step-text-body");
        if (!content) return null;
        const section = document.createElement("section");
        section.className = `step-text-section${className ? " " + className : ""}`;
        const h = document.createElement("h3");
        h.textContent = title;
        const iconEl = icon ? makeAssetIcon(null, title, icon) : null;
        if (iconEl) {
            const head = document.createElement("div");
            head.className = "asset-heading section-heading";
            head.appendChild(iconEl);
            head.appendChild(h);
            section.appendChild(head);
        } else {
            section.appendChild(h);
        }
        section.appendChild(content);
        return section;
    }

    function renderDesignMove(description) {
        return renderStepTextSection("Design Rationale", description, "education-card design-move", ICON_FALLBACK.designMove);
    }

    function renderDecisionPoint(prompt) {
        return renderStepTextSection("Decision Point", prompt, "education-card decision-prompt top-decision-prompt", ICON_FALLBACK.decisionPoint);
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

    function renderTopConcepts(concepts, opts) {
        opts = opts || {};
        if (!Array.isArray(concepts) || concepts.length === 0) return null;
        function makeConceptCard(concept) {
            const card = document.createElement("article");
            card.className = "concept-card";
            if (typeof concept === "string") {
                const p = document.createElement("p");
                p.textContent = concept;
                card.appendChild(p);
            } else if (concept && typeof concept === "object") {
                const term = concept.term || concept.name || concept.title || "Concept";
                const head = document.createElement("div");
                head.className = "asset-heading";
                const icon = makeAssetIcon(concept.icon, `${term} icon`, ICON_FALLBACK.concept);
                if (icon) head.appendChild(icon);
                const h = document.createElement("h4");
                h.textContent = term;
                head.appendChild(h);
                card.appendChild(head);
                if (concept.definition || concept.description) {
                    const p = document.createElement("p");
                    p.className = "concept-definition";
                    p.textContent = concept.definition || concept.description;
                    card.appendChild(p);
                }
                appendConceptLine(card, "Why it matters", concept.whyItMatters || concept.why);
                appendConceptLine(card, "Example", concept.example);
                if (opts.showSteps && Array.isArray(concept.steps) && concept.steps.length > 0) {
                    card.appendChild(makeStepChips(concept.steps));
                }
            }
            return card.children.length > 0 ? card : null;
        }

        const wrap = document.createElement("div");
        wrap.className = "step-concepts" + (opts.className ? ` ${opts.className}` : "");
        if (opts.showTitle !== false) {
            const h = document.createElement("h3");
            h.textContent = opts.title || "Concepts introduced";
            wrap.appendChild(h);
        }

        if (opts.grouped) {
            for (const group of groupedIntroItems(concepts, opts.fallbackGroup || "Concepts")) {
                const section = document.createElement("section");
                section.className = "intro-item-group";
                const title = document.createElement("h3");
                title.className = "intro-item-group-title";
                title.textContent = group.name;
                section.appendChild(title);

                const grid = document.createElement("div");
                grid.className = "concept-grid";
                for (const concept of group.items) {
                    const card = makeConceptCard(concept);
                    if (card) grid.appendChild(card);
                }
                if (grid.children.length > 0) {
                    section.appendChild(grid);
                    wrap.appendChild(section);
                }
            }
            return wrap.children.length > (opts.showTitle === false ? 0 : 1) ? wrap : null;
        }

        const cards = [];
        for (const concept of concepts) {
            const card = makeConceptCard(concept);
            if (card) cards.push(card);
        }
        if (cards.length === 0) return null;

        const grid = document.createElement("div");
        grid.className = "concept-grid";
        cards.forEach((card) => grid.appendChild(card));
        wrap.appendChild(grid);
        return wrap;
    }

    function renderDescription(description, whyNow, decisionPrompt) {
        els.stepDescription.innerHTML = "";
        const designMove = renderDesignMove(description);
        if (designMove) els.stepDescription.appendChild(designMove);
        const whyNowSection = renderWhyNow(whyNow);
        if (whyNowSection) els.stepDescription.appendChild(whyNowSection);
        const decisionPoint = renderDecisionPoint(decisionPrompt);
        if (decisionPoint) els.stepDescription.appendChild(decisionPoint);
    }

    // ---------- Rendering: architecture step diagram + options ----------

    function mermaidSafeId(id, prefix) {
        const raw = String(id || "").trim();
        const safe = raw.replace(/[^A-Za-z0-9_-]/g, "_");
        if (/^[A-Za-z_]/.test(safe)) return safe || `${prefix || "N"}_`;
        return `${prefix || "N"}_${safe}`;
    }

    function mermaidSequenceSafeId(id, used) {
        const raw = String(id || "").trim();
        let safe = raw.replace(/[^A-Za-z0-9_]/g, "_");
        if (!safe) safe = "P";
        if (!/^[A-Za-z_]/.test(safe)) safe = `P_${safe}`;
        const base = safe;
        let i = 2;
        while (used.has(safe)) {
            safe = `${base}_${i}`;
            i += 1;
        }
        used.add(safe);
        return safe;
    }

    // Encode characters the Mermaid flowchart parser treats as structural
    // tokens (shape brackets, label pipes, quotes) as Mermaid entities. Mermaid
    // decodes these back to the real glyphs when rendering, so the displayed
    // text is unchanged while the source stays parseable. Used for both node
    // and edge labels in generated flowcharts.
    function mermaidLabelEscape(label) {
        return String(label || "")
            .replace(/&/g, "#38;")
            .replace(/"/g, "&quot;")
            .replace(/\(/g, "#40;")
            .replace(/\)/g, "#41;")
            .replace(/\[/g, "#91;")
            .replace(/\]/g, "#93;")
            .replace(/\{/g, "#123;")
            .replace(/\}/g, "#125;")
            .replace(/\|/g, "#124;");
    }

    function mermaidNodeLabel(label) {
        return mermaidLabelEscape(label);
    }

    function mermaidSequenceText(text) {
        return String(text || "").replace(/\s+/g, " ").trim();
    }

    function graphShapeLine(id, label, shape) {
        // label is already entity-escaped by mermaidNodeLabel, so special
        // characters in the text won't be parsed as extra shape tokens.
        if (shape === "database") {
            return `  ${id}[(${label})]`;
        }
        if (shape === "queue" || shape === "subroutine") {
            return `  ${id}[[${label}]]`;
        }
        if (shape === "cache" || shape === "stadium") {
            return `  ${id}([${label}])`;
        }
        if (shape === "external" || shape === "actor" || shape === "parallelogram") {
            return `  ${id}[/${label}/]`;
        }
        if (shape === "diamond") return `  ${id}{${label}}`;
        if (shape === "circle") return `  ${id}((${label}))`;
        if (shape === "asymmetric") return `  ${id}>${label}]`;
        return `  ${id}[${label}]`;
    }

    function graphNodeLine(node, render) {
        const id = mermaidSafeId(node.id, "N");
        const label = mermaidNodeLabel((render && render.label) || node.label || node.id);
        const style = nodeTypeStyle(node.type);
        const shape = render && render.shape ? String(render.shape) : (style && style.shape ? style.shape : "rect");
        return graphShapeLine(id, label, shape);
    }

    function graphLinkLine(link) {
        if (!link || !link.from || !link.to) return "";
        const from = mermaidSafeId(link.from, "N");
        const to = mermaidSafeId(link.to, "N");
        const render = link.render && typeof link.render === "object" ? link.render : {};
        const arrow = String(render.arrow || (render.style === "dashed" ? "-.->" : "-->"));
        const label = String(link.label || "").trim();
        // Entity-escape so parentheses/brackets/pipes in the text aren't parsed
        // as Mermaid node-shape or label-delimiter tokens; Mermaid decodes the
        // entities back to the real glyphs when rendering.
        const escaped = mermaidLabelEscape(label);
        return label ? `  ${from} ${arrow}|${escaped}| ${to}` : `  ${from} ${arrow} ${to}`;
    }

    function graphViewRefs(view, key) {
        if (!view || typeof view !== "object") return [];
        const value = view[key];
        return Array.isArray(value) ? value : [];
    }

    function linkFromRef(ref) {
        if (typeof ref === "string") return state.linkIndex && state.linkIndex.get(ref);
        if (ref && typeof ref === "object") return ref;
        return null;
    }

    function graphViewToMermaid(view) {
        if (!hasGraphView(view)) return "";
        const nodeRefs = graphViewRefs(view, "nodes");
        const nodeMetas = [];
        const nodeIds = new Set();

        nodeRefs.forEach((ref) => {
            const meta = nodeMetadataForRef(ref);
            if (!meta || !meta.id) return;
            const render = normalizeNodeRef(ref).render || (meta.render && typeof meta.render === "object" ? meta.render : null);
            nodeMetas.push({meta, render});
            nodeIds.add(meta.id);
        });

        const links = graphViewRefs(view, "links")
            .map(linkFromRef)
            .filter((link) => link && link.from && link.to)
            .filter((link) => nodeIds.has(link.from) && nodeIds.has(link.to));

        links.forEach((link) => {
            [link.from, link.to].forEach((id) => {
                if (nodeIds.has(id)) return;
                const meta = nodeMetadataForRef(id);
                if (meta && meta.id) {
                    nodeMetas.push({meta, render: null});
                    nodeIds.add(meta.id);
                }
            });
        });

        const lines = ["graph TB"];
        const emitted = new Set();
        const groupRefs = graphViewRefs(view, "groups");
        groupRefs.forEach((groupRef) => {
            const groupId = typeof groupRef === "string" ? groupRef : groupRef && groupRef.id;
            const group = groupId && state.architectureTypeIndex ? state.architectureTypeIndex.get(groupId) : null;
            if (!group || !Array.isArray(group.nodes)) return;
            const grouped = nodeMetas.filter((item) => group.nodes.includes(item.meta.id));
            if (grouped.length === 0) return;
            lines.push(`  subgraph ${mermaidSafeId(group.id, "G")}["${mermaidNodeLabel(group.label || group.id)}"]`);
            grouped.forEach((item) => {
                lines.push(graphNodeLine(item.meta, item.render));
                emitted.add(item.meta.id);
            });
            lines.push("  end");
        });

        nodeMetas.forEach((item) => {
            if (emitted.has(item.meta.id)) return;
            lines.push(graphNodeLine(item.meta, item.render));
            emitted.add(item.meta.id);
        });
        links.forEach((link) => {
            const line = graphLinkLine(link);
            if (line) lines.push(line);
        });
        return lines.join("\n");
    }

    function normalizeSequenceParticipant(ref) {
        if (typeof ref === "string") return {id: String(ref).trim(), label: ""};
        if (!ref || typeof ref !== "object") return {id: "", label: ""};
        const id = String(ref.id || ref.node || ref.ref || ref.alias || ref.label || "").trim();
        return {
            id,
            alias: String(ref.alias || "").trim(),
            label: ref.label !== undefined ? normalizeNodeLookupLabel(ref.label) : "",
            kind: String(ref.kind || "").trim().toLowerCase(),
            actor: ref.actor === true,
        };
    }

    function collectSequenceMessageRefs(messages, out) {
        if (!Array.isArray(messages)) return;
        messages.forEach((msg) => {
            if (!msg || typeof msg !== "object") return;
            if (msg.from) out.add(String(msg.from).trim());
            if (msg.to) out.add(String(msg.to).trim());
            if (Array.isArray(msg.over)) msg.over.forEach((id) => out.add(String(id).trim()));
            if (msg.of) out.add(String(msg.of).trim());
            collectSequenceMessageRefs(msg.messages, out);
            if (msg.else && typeof msg.else === "object") collectSequenceMessageRefs(msg.else.messages, out);
            if (Array.isArray(msg.branches)) {
                msg.branches.forEach((branch) => collectSequenceMessageRefs(branch && branch.messages, out));
            }
        });
    }

    function sequenceParticipantSpecs(sequence) {
        const participants = sequence && Array.isArray(sequence.participants)
            ? sequence.participants
            : [];
        const specs = [];
        const byId = new Map();
        const usedAliases = new Set();

        function addParticipant(ref) {
            const raw = normalizeSequenceParticipant(ref);
            if (!raw.id) return null;
            if (byId.has(raw.id)) return byId.get(raw.id);
            const meta = nodeMetadataFor(raw.id, raw.label || "");
            const label = raw.label || (meta && meta.label) || raw.id;
            let alias;
            if (raw.alias && /^[A-Za-z_][A-Za-z0-9_]*$/.test(raw.alias) && !usedAliases.has(raw.alias)) {
                alias = raw.alias;
                usedAliases.add(alias);
            } else {
                alias = mermaidSequenceSafeId(raw.id, usedAliases);
            }
            const spec = {
                id: raw.id,
                alias,
                label,
                actor: raw.actor || raw.kind === "actor" || (meta && meta.type === "actor"),
            };
            specs.push(spec);
            byId.set(raw.id, spec);
            if (raw.alias) byId.set(raw.alias, spec);
            return spec;
        }

        participants.forEach(addParticipant);

        const referenced = new Set();
        collectSequenceMessageRefs(sequence && sequence.messages, referenced);
        referenced.forEach((id) => {
            if (!id || byId.has(id)) return;
            addParticipant({id});
        });

        const aliasByRef = new Map();
        const nodeByAlias = new Map();
        specs.forEach((spec) => {
            aliasByRef.set(spec.id, spec.alias);
            aliasByRef.set(spec.alias, spec.alias);
            nodeByAlias.set(spec.alias, spec.id);
        });

        return {specs, aliasByRef, nodeByAlias};
    }

    function appendSequenceMessages(lines, messages, aliasByRef, indent) {
        if (!Array.isArray(messages)) return;
        const pad = "  ".repeat(indent || 1);

        function refAlias(ref) {
            const id = String(ref || "").trim();
            return aliasByRef.get(id) || mermaidSequenceSafeId(id || "P", new Set());
        }

        messages.forEach((msg) => {
            if (!msg || typeof msg !== "object") return;
            const type = String(msg.type || "").trim().toLowerCase();

            if (msg.from && msg.to) {
                const arrow = String(msg.arrow || "->>").trim() || "->>";
                lines.push(`${pad}${refAlias(msg.from)}${arrow}${refAlias(msg.to)}: ${mermaidSequenceText(msg.label || msg.message || "")}`);
                return;
            }

            if (type === "note") {
                const over = Array.isArray(msg.over)
                    ? msg.over.map(refAlias).join(",")
                    : refAlias(msg.of || msg.to || msg.from);
                const position = String(msg.position || "over").trim() || "over";
                lines.push(`${pad}Note ${position} ${over}: ${mermaidSequenceText(msg.label || msg.text || msg.message || "")}`);
                return;
            }

            if (type === "activate" || type === "deactivate") {
                lines.push(`${pad}${type} ${refAlias(msg.participant || msg.id || msg.of)}`);
                return;
            }

            if (type === "alt") {
                lines.push(`${pad}alt ${mermaidSequenceText(msg.label || msg.condition || "")}`);
                appendSequenceMessages(lines, msg.messages, aliasByRef, (indent || 1) + 1);
                if (msg.else && typeof msg.else === "object") {
                    lines.push(`${pad}else ${mermaidSequenceText(msg.else.label || msg.else.condition || "")}`);
                    appendSequenceMessages(lines, msg.else.messages, aliasByRef, (indent || 1) + 1);
                }
                lines.push(`${pad}end`);
                return;
            }

            if (type === "loop" || type === "opt" || type === "critical" || type === "break") {
                lines.push(`${pad}${type} ${mermaidSequenceText(msg.label || msg.condition || "")}`);
                appendSequenceMessages(lines, msg.messages, aliasByRef, (indent || 1) + 1);
                lines.push(`${pad}end`);
                return;
            }

            if (type === "par") {
                lines.push(`${pad}par ${mermaidSequenceText(msg.label || "")}`);
                appendSequenceMessages(lines, msg.messages, aliasByRef, (indent || 1) + 1);
                (msg.branches || []).forEach((branch) => {
                    lines.push(`${pad}and ${mermaidSequenceText(branch && branch.label || "")}`);
                    appendSequenceMessages(lines, branch && branch.messages, aliasByRef, (indent || 1) + 1);
                });
                lines.push(`${pad}end`);
                return;
            }

            if (type === "raw" && msg.line) {
                lines.push(`${pad}${String(msg.line).trim()}`);
            }
        });
    }

    function sequenceToMermaid(sequence) {
        if (!hasSequence(sequence)) return "";
        const {specs, aliasByRef} = sequenceParticipantSpecs(sequence);
        if (specs.length === 0) return "";
        const lines = ["sequenceDiagram"];
        if (sequence.autonumber) lines.push("  autonumber");
        if (sequence.title) lines.push(`  title ${mermaidSequenceText(sequence.title)}`);
        specs.forEach((spec) => {
            const keyword = spec.actor ? "actor" : "participant";
            const label = mermaidSequenceText(spec.label || spec.id);
            lines.push(label && label !== spec.alias
                ? `  ${keyword} ${spec.alias} as ${label}`
                : `  ${keyword} ${spec.alias}`);
        });
        appendSequenceMessages(lines, sequence.messages, aliasByRef, 1);
        return lines.join("\n");
    }

    function flowDiagramSource(flow) {
        if (!flow || typeof flow !== "object") return "";
        return sequenceToMermaid(flow.sequence);
    }

    function sequenceParticipantNodeMap(sequence) {
        if (!hasSequence(sequence)) return null;
        return sequenceParticipantSpecs(sequence).nodeByAlias;
    }

    function flowParticipantNodeMap(flow) {
        return flow && hasSequence(flow.sequence) ? sequenceParticipantNodeMap(flow.sequence) : null;
    }

    function hasFlowDiagram(flow) {
        return !!(flow && hasSequence(flow.sequence));
    }

    function effectiveDiagramFor(step) {
        if (Array.isArray(step.options) && step.options.length > 0) {
            const opt = step.options[state.currentOptionIndex] || step.options[0];
            const viewDiagram = graphViewToMermaid(opt.view || step.view);
            return {
                diagram: viewDiagram,
                highlight: opt.view && Array.isArray(opt.view.highlight)
                        ? opt.view.highlight
                        : (step.view && Array.isArray(step.view.highlight) ? step.view.highlight : []),
            };
        }
        const viewDiagram = graphViewToMermaid(step.view);
        return {
            diagram: viewDiagram,
            highlight: step.view && Array.isArray(step.view.highlight) ? step.view.highlight : [],
        };
    }

    function defaultDiagramFor(step) {
        if (!step) return "";
        if (Array.isArray(step.options) && step.options.length > 0) {
            return graphViewToMermaid(step.options[0].view || step.view);
        }
        return graphViewToMermaid(step.view);
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

    // Node ids a step focuses on: the nodes its view (or current option's view)
    // actually contains. Used to highlight the step's piece within the full
    // (final-design) architecture in the "Full context" view.
    function stepFocusNodeIds(step) {
        if (!step) return [];
        let view = step.view;
        if (Array.isArray(step.options) && step.options.length > 0) {
            const opt = step.options[state.currentOptionIndex] || step.options[0];
            view = (opt && opt.view) || step.view;
        }
        const ids = graphViewRefs(view, "nodes").map((ref) =>
            typeof ref === "string" ? ref : (ref && ref.id ? ref.id : "")
        ).filter(Boolean);
        return [...new Set(ids)];
    }

    // The "Full context" diagram is the final design (the complete target
    // architecture). The current step's focus nodes are highlighted within it,
    // so the reader always sees the whole system and where this step fits.
    // Falls back to the accumulated prior-steps merge if no final design exists.
    function fullContextDiagramFor(entryIndex, currentDiagram) {
        const entry = state.entries[entryIndex];
        if (!entry || entry.kind !== "step") return currentDiagram;

        const finalDesign = resolveFinalDesign(state.data);
        const finalView = finalDesign && finalDesign.view;
        const finalDiagram = graphViewToMermaid(finalView);
        if (finalDiagram) return finalDiagram;

        // Fallback: no final design — accumulate the diagrams up to this step.
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

    // Highlight set for the "Full context" view: the current step's focus nodes,
    // restricted to nodes that actually appear in the full-context diagram.
    function fullContextHighlightFor(step, contextDiagram) {
        const focus = stepFocusNodeIds(step);
        if (focus.length === 0) return [];
        const present = extractNodeIds(contextDiagram);
        const filtered = focus.filter((id) => present.has(id));
        return filtered.length > 0 ? filtered : focus;
    }

    // Small legend under the diagram explaining the crimson highlight. Shown
    // only when at least one node is highlighted; wording reflects the view.
    function renderDiagramLegend(highlightCount) {
        const el = els.diagramLegend;
        if (!el) return;
        if (!highlightCount) {
            el.hidden = true;
            return;
        }
        const text = state.currentDiagramView === "context"
            ? "this step’s nodes within the full design"
            : "in focus this step";
        const textEl = el.querySelector(".diagram-legend-text");
        if (textEl) textEl.textContent = text;
        el.hidden = false;
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
            renderDiagramLegend(Array.isArray(highlights) ? highlights.length : 0);
        } catch (err) {
            els.diagram.innerHTML = "";
            renderDiagramLegend(0);
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
            btn.textContent = `${idx + 1}. ${opt.name || opt.title || "Option"}`;
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
        // Fallback shape: some datasets author options as
        // { title, description, tradeoffs[] } instead of { name, pros, cons }.
        const tradeoffs = Array.isArray(opt.tradeoffs) ? opt.tradeoffs : [];
        if (pros.length === 0 && cons.length === 0 && tradeoffs.length === 0) {
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

        if (pros.length > 0 || cons.length > 0) {
            if (pros.length > 0) els.optionProsCons.appendChild(col("Pros", pros, "pros"));
            if (cons.length > 0) els.optionProsCons.appendChild(col("Cons", cons, "cons"));
        } else {
            els.optionProsCons.appendChild(col("Tradeoffs", tradeoffs, "tradeoffs"));
        }
    }

    // One-line "what this alternative is", shown between the option tabs and the
    // diagram. Works for both option shapes (name/pros/cons and title/tradeoffs).
    function renderOptionDescription(step) {
        els.optionDescription.innerHTML = "";
        if (!Array.isArray(step.options) || step.options.length === 0) {
            els.optionDescription.hidden = true;
            return;
        }
        const opt = step.options[state.currentOptionIndex] || step.options[0];
        const desc = typeof opt.description === "string" ? opt.description.trim() : "";
        if (!desc) {
            els.optionDescription.hidden = true;
            return;
        }
        els.optionDescription.hidden = false;
        els.optionDescription.textContent = desc;
    }

    // ---------- Rendering: per-step extras ----------

    // `icon` is an optional site-root fallback path; when set, the section's
    // <h3> title is shown alongside that icon (same .asset-heading treatment).
    function makeSection(title, contentEl, className, icon) {
        const wrap = document.createElement("section");
        wrap.className = `extras-section${className ? " " + className : ""}`;
        const h = document.createElement("h3");
        h.textContent = title;
        const iconEl = icon ? makeAssetIcon(null, title, icon) : null;
        if (iconEl) {
            const head = document.createElement("div");
            head.className = "asset-heading section-heading";
            head.appendChild(iconEl);
            head.appendChild(h);
            wrap.appendChild(head);
        } else {
            wrap.appendChild(h);
        }
        wrap.appendChild(contentEl);
        return wrap;
    }

    // `icon` is a site-root fallback path (e.g. ICON_FALLBACK.before); when set,
    // the label heading is shown with that icon (same treatment as concepts).
    function makeLabeledText(label, value, icon) {
        const wrap = document.createElement("div");
        wrap.className = "labeled-text";
        const h = document.createElement("h4");
        h.textContent = label;
        const iconEl = icon ? makeAssetIcon(null, label, icon) : null;
        if (iconEl) {
            const head = document.createElement("div");
            head.className = "asset-heading";
            head.appendChild(iconEl);
            head.appendChild(h);
            wrap.appendChild(head);
        } else {
            wrap.appendChild(h);
        }
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
        return renderStepTextSection("Why Now", whyNow, "education-card why-now", ICON_FALLBACK.whyNow);
    }

    function renderRecap(recap) {
        if (!recap) return null;
        if (typeof recap === "string" || Array.isArray(recap)) {
            const content = renderTextOrBullets(recap, "education-card");
            return content ? makeSection("Recap", content, "recap") : null;
        }

        const fields = [
            ["Before", recap.before, ICON_FALLBACK.before],
            ["After", recap.after, ICON_FALLBACK.after],
            ["New risk", recap.newRisk, ICON_FALLBACK.risk],
        ].filter((pair) => pair[1]);
        if (fields.length === 0) return null;

        const wrap = document.createElement("div");
        wrap.className = "recap-grid";
        fields.forEach(([label, value, icon]) => {
            wrap.appendChild(makeLabeledText(label, value, icon));
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
            const head = document.createElement("div");
            head.className = "asset-heading";
            const icon = makeAssetIcon(null, "Failure drill", ICON_FALLBACK.failureDrill);
            if (icon) head.appendChild(icon);
            const h = document.createElement("h4");
            h.textContent = scenario;
            head.appendChild(h);
            card.appendChild(head);
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
            const head = document.createElement("div");
            head.className = "asset-heading";
            const icon = makeAssetIcon(null, "Trap", ICON_FALLBACK.trap);
            if (icon) head.appendChild(icon);
            const h = document.createElement("h4");
            h.textContent = t.trap || t.title || "Trap";
            head.appendChild(h);
            card.appendChild(head);
            if (t.why) card.appendChild(makeLabeledText("Why it's wrong", t.why));
            if (t.instead || t.better) card.appendChild(makeLabeledText("Do instead", t.instead || t.better));
            wrap.appendChild(card);
        }
        return wrap.children.length > 0 ? makeSection("Common traps", wrap, "traps") : null;
    }

    function normalizedPatternKey(value) {
        return String(value || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, " ")
            .trim();
    }

    function datasetPatternIndex() {
        const index = new Map();
        const collections = [
            state.data && state.data.patterns,
            state.data && state.data.patternCatalog,
        ];
        for (const collection of collections) {
            for (const item of Array.isArray(collection) ? collection : []) {
                if (!item || typeof item !== "object") continue;
                for (const key of [item.name, item.id, item.title]) {
                    const normalized = normalizedPatternKey(key);
                    if (normalized && !index.has(normalized)) index.set(normalized, item);
                }
            }
        }
        return index;
    }

    // Per-step patterns use the same visual treatment as concepts. Step arrays
    // usually contain names; details/icons resolve from dataset-level patterns.
    function renderStepPatterns(patterns) {
        if (!Array.isArray(patterns) || patterns.length === 0) return null;
        const index = datasetPatternIndex();
        const cards = [];
        for (const item of patterns) {
            const inline = item && typeof item === "object" ? item : null;
            const name = inline
                ? (inline.name || inline.title || inline.id || "Pattern")
                : String(item || "");
            const meta = Object.assign({}, index.get(normalizedPatternKey(name)) || {}, inline || {});
            const title = meta.name || meta.title || name;
            if (!title) continue;

            const card = document.createElement("article");
            card.className = "concept-card pattern-concept-card";

            const head = document.createElement("div");
            head.className = "asset-heading";
            const icon = makeAssetIcon(meta.icon, `${title} icon`, ICON_FALLBACK.pattern);
            if (icon) head.appendChild(icon);
            const h = document.createElement("h4");
            h.textContent = title;
            head.appendChild(h);
            card.appendChild(head);

            if (meta.what || meta.description) {
                const p = document.createElement("p");
                p.className = "concept-definition";
                p.textContent = meta.what || meta.description;
                card.appendChild(p);
            }
            appendConceptLine(card, "When to use", meta.whenToUse);
            appendConceptLine(card, "Trade-off", meta.tradeoffs || meta.tradeoff);
            cards.push(card);
        }
        if (cards.length === 0) return null;

        const wrap = document.createElement("div");
        wrap.className = "step-concepts step-pattern-cards";
        const h = document.createElement("h3");
        h.textContent = "Used Patterns";
        wrap.appendChild(h);
        const grid = document.createElement("div");
        grid.className = "concept-grid";
        cards.forEach((card) => grid.appendChild(card));
        wrap.appendChild(grid);
        return wrap;
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

        if (Array.isArray(step.flows) && step.flows.length > 0) {
            // Only render valid flows (must have a non-empty diagram source).
            const validFlows = step.flows.filter(
                (f) => hasFlowDiagram(f)
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
                const flowSrc = flowDiagramSource(flow);
                body.appendChild(makeMermaidEl(flowSrc, "flow-diagram", {
                    highlightParticipants: flowHighlights,
                    sourceForLabels: flowSrc,
                    annotateParticipants: true,
                    participantNodeIds: flowParticipantNodeMap(flow),
                }));
                wrap.appendChild(body);

                els.stepExtras.appendChild(makeSection("Flows", wrap, "flows"));
            }
        }

        appendStepExtra(renderTopConcepts(step.concepts));
        appendStepExtra(renderStepPatterns(step.patterns));

        appendStepExtra(renderRecap(step.recap));
        appendStepExtra(renderFailureDrills(step.failureDrills));
        appendStepExtra(renderTraps(step.traps));

        if (Array.isArray(step.deepDives) && step.deepDives.length > 0) {
            const wrap = document.createElement("div");
            wrap.className = "deepdive-list";
            for (const dd of step.deepDives) {
                const card = document.createElement("div");
                card.className = "deepdive-card";
                const head = document.createElement("div");
                head.className = "asset-heading";
                const ddIcon = makeAssetIcon(null, "Deep dive", ICON_FALLBACK.deepDive);
                if (ddIcon) head.appendChild(ddIcon);
                const h = document.createElement("h4");
                h.textContent = dd.title || "Deep dive";
                head.appendChild(h);
                card.appendChild(head);
                card.appendChild(makeBulletList(bulletsFrom(dd.points || [])));
                if (hasGraphView(dd.view)) {
                    card.appendChild(makeMermaidEl(graphViewToMermaid(dd.view), "deepdive-diagram"));
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
                const icon = makeAssetIcon(null, "Bottleneck / mitigation", ICON_FALLBACK.mitigations);
                if (icon) row.appendChild(icon);
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
            els.stepExtras.appendChild(makeSection("Talking points", makeBulletList(step.talkingPoints), "talking", ICON_FALLBACK.talkingPoints));
        }

        appendStepExtra(renderInterviewerSignals(step.interviewerSignals));

        if (Array.isArray(step.followUps) && step.followUps.length > 0) {
            els.stepExtras.appendChild(makeSection("Follow-up questions", makeBulletList(step.followUps), "followups"));
        }

        appendStepExtra(renderStepProbeLinks(step.probeLinks));
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
    function applySequenceHighlights(targetEl, idToLabel, highlightIds, idToNodeId) {
        if (!highlightIds || highlightIds.length === 0) return;
        const labels = new Set();
        for (const id of highlightIds) {
            if (idToLabel.has(id)) labels.add(idToLabel.get(id));
            labels.add(id); // also match the bare id, in case it's used as label
            if (idToNodeId && idToNodeId.size > 0) {
                idToNodeId.forEach((nodeId, participantId) => {
                    if (nodeId !== id) return;
                    labels.add(participantId);
                    if (idToLabel.has(participantId)) labels.add(idToLabel.get(participantId));
                });
            }
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

    function setSvgStyle(el, prop, value) {
        if (!el || !value || !el.style || !el.style.setProperty) return;
        el.style.setProperty(prop, value, "important");
    }

    function applyConfiguredNodeTypeStyle(textEl, rects, style) {
        if (!style) return;
        if (style.className) {
            textEl.classList.add(style.className);
            rects.forEach((r) => r.classList.add(style.className));
        }
        rects.forEach((r) => {
            setSvgStyle(r, "fill", style.fill);
            setSvgStyle(r, "stroke", style.stroke);
            setSvgStyle(r, "stroke-width", style.strokeWidth);
        });
        setSvgStyle(textEl, "fill", style.color);
    }

    function applySequenceParticipantTypes(targetEl, idToLabel, idToNodeId) {
        if (!idToLabel || idToLabel.size === 0) return;
        const svg = targetEl.querySelector("svg");
        if (!svg) return;

        const byLabel = new Map();
        idToLabel.forEach((label, id) => {
            const nodeId = idToNodeId && idToNodeId.has(id) ? idToNodeId.get(id) : id;
            byLabel.set(label, {id, nodeId, label});
            byLabel.set(id, {id, nodeId, label});
            if (nodeId !== id) byLabel.set(nodeId, {id, nodeId, label});
        });

        const ns = svg.namespaceURI || "http://www.w3.org/2000/svg";
        const texts = svg.querySelectorAll("text");
        texts.forEach((t) => {
            if (t.dataset && t.dataset.participantTypeAnnotated === "true") return;
            const txt = (t.textContent || "").trim();
            const participant = byLabel.get(txt);
            if (!participant) return;
            if (actorRectsForText(t).length === 0) return;

            const meta = nodeMetadataFor(participant.nodeId, participant.label);
            const type = meta ? meta.type : "";
            if (!type) return;
            const style = nodeTypeStyle(type);
            const rects = actorRectsForText(t);
            applyConfiguredNodeTypeStyle(t, rects, style);

            const x = t.getAttribute("x");
            t.textContent = "";
            if (t.dataset) t.dataset.participantTypeAnnotated = "true";

            const typeLine = document.createElementNS(ns, "tspan");
            typeLine.textContent = canonicalNodeType(type).toUpperCase();
            typeLine.setAttribute("class", "sequence-node-type-caption");
            if (style) setSvgStyle(typeLine, "fill", style.captionColor);
            if (x !== null) typeLine.setAttribute("x", x);
            // Mermaid centers the original participant label vertically. Pull the
            // first tspan up so the smaller type caption does not float too low.
            typeLine.setAttribute("dy", "-1.1em");

            const labelLine = document.createElementNS(ns, "tspan");
            labelLine.textContent = participant.label;
            labelLine.setAttribute("class", "sequence-node-main-label");
            if (style) setSvgStyle(labelLine, "fill", style.color);
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
    // sourceForLabels, annotateParticipants, annotateNodeTypes }`
    // for sequence diagrams. We can't use Mermaid's `classDef`/`class` syntax
    // there (the sequence parser rejects it), so instead we patch the rendered
    // SVG to tag participant boxes whose label matches a highlighted id.
    function makeMermaidEl(diagramSrc, className, opts) {
        diagramSrc = diagramSource(diagramSrc);
        const annotateNodeTypes = !opts || opts.annotateNodeTypes !== false;
        const renderSrc = annotateNodeTypes ? annotateFlowchartNodeTypes(diagramSrc) : diagramSrc;
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
                    const participantNodeIds = opts.participantNodeIds || null;
                    if (Array.isArray(opts.highlightParticipants) && opts.highlightParticipants.length > 0) {
                        applySequenceHighlights(target, labelMap, opts.highlightParticipants, participantNodeIds);
                    }
                    if (opts.annotateParticipants) {
                        applySequenceParticipantTypes(target, labelMap, participantNodeIds);
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

    // A dataModel field may be authored as an object ({ name, type?, note? })
    // or as a bare string (just the field name). Normalize so both render.
    function normalizeField(f) {
        if (typeof f === "string") return {name: f};
        if (f && typeof f === "object") return f;
        return {name: String(f == null ? "" : f)};
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
            for (const rawF of t.fields || []) {
                const f = normalizeField(rawF);
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
        const description = state.data && String(state.data.description || "").trim();
        if (description) {
            const list = makeBulletList(bulletsFrom(description), "dataset-description muted");
            list.id = "dataset-description";
            outer.appendChild(list);
        }
        if (state.data && hasDiagram(state.data.requirementsDiagram)) {
            // Requirements diagrams lay out left-to-right.
            outer.appendChild(makeMermaidEl(forceFlowchartDirection(state.data.requirementsDiagram, "LR"), "requirements-diagram", {
                annotateNodeTypes: false,
            }));
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
            outer.appendChild(makeMermaidEl(forceFlowchartDirection(state.data.capacityDiagram, "LR"), "capacity-diagram", {
                annotateNodeTypes: false,
            }));
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

            if (hasFlowDiagram(r)) {
                const flowSrc = flowDiagramSource(r);
                card.appendChild(makeMermaidEl(flowSrc, "api-diagram", {
                    annotateParticipants: true,
                    sourceForLabels: flowSrc,
                    participantNodeIds: flowParticipantNodeMap(r),
                }));
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
            const tableNote = t.note || t.notes;
            if (tableNote) {
                const n = document.createElement("p");
                n.className = "muted schema-note";
                n.textContent = tableNote;
                card.appendChild(n);
            }
            const tbl = document.createElement("table");
            tbl.className = "schema-table";
            const thead = document.createElement("thead");
            thead.innerHTML = "<tr><th>Field</th><th>Type</th><th>Note</th></tr>";
            tbl.appendChild(thead);
            const tbody = document.createElement("tbody");
            for (const rawF of t.fields || []) {
                const f = normalizeField(rawF);
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

    function renderProbeFurtherLinkList(links) {
        const list = document.createElement("ul");
        list.className = "probe-links";
        for (const item of links) {
            if (!item || typeof item !== "object") continue;
            const li = document.createElement("li");
            li.className = "probe-link-item";

            const titleText = item.title || item.name || item.url || "Resource";
            if (item.url) {
                const a = document.createElement("a");
                a.className = "probe-link-title";
                a.href = item.url;
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.textContent = titleText;
                li.appendChild(a);
            } else {
                const h = document.createElement("div");
                h.className = "probe-link-title";
                h.textContent = titleText;
                li.appendChild(h);
            }

            const metaParts = [item.source, item.type, item.year]
                .map((part) => String(part || "").trim())
                .filter(Boolean);
            if (metaParts.length > 0) {
                const meta = document.createElement("span");
                meta.className = "probe-link-meta mono";
                meta.textContent = ` ${metaParts.join(" / ")}`;
                li.appendChild(meta);
            }

            const why = item.why || item.description || item.note;
            if (why) {
                const p = document.createElement("p");
                p.className = "probe-link-why";
                p.textContent = why;
                li.appendChild(p);
            }

            list.appendChild(li);
        }
        return list;
    }

    function renderStepProbeLinks(linkIds) {
        if (!Array.isArray(linkIds) || linkIds.length === 0) return null;
        const index = probeFurtherLinkIndex();
        const links = linkIds
            .map((id) => index.get(String(id || "").trim()))
            .filter(Boolean);
        if (links.length === 0) return null;
        return makeSection("To Probe Further", renderProbeFurtherLinkList(links), "probe-further-step");
    }

    // Wrap-up > To Probe Further. Grouped external reading list.
    function renderIntroToProbeFurther(payload) {
        const outer = document.createElement("div");
        outer.className = "probe-further";

        const groups = probeFurtherGroups(payload);
        for (const group of groups) {
            if (!group || typeof group !== "object") continue;
            const links = Array.isArray(group.links) ? group.links : [];
            if (links.length === 0) continue;

            const section = document.createElement("section");
            section.className = "probe-group";

            const title = document.createElement("h3");
            title.className = "probe-group-title";
            title.textContent = group.group || group.title || "Further reading";
            section.appendChild(title);

            if (group.description) {
                const desc = document.createElement("p");
                desc.className = "probe-group-description muted";
                desc.textContent = group.description;
                section.appendChild(desc);
            }

            section.appendChild(renderProbeFurtherLinkList(links));
            outer.appendChild(section);
        }

        return outer;
    }

    // Overview > Patterns. Each item: { name, what, whenToUse?, steps? }.
    // Names the reusable design patterns this case teaches and links them to
    // the steps where they appear.
    function renderIntroPatterns(items) {
        const patterns = Array.isArray(items) ? items : [];
        function makePatternCard(p) {
            p = p && typeof p === "object" ? p : {name: String(p || "")};
            const card = document.createElement("div");
            card.className = "pattern-card";

            const head = document.createElement("div");
            head.className = "asset-heading pattern-heading";
            const icon = makeAssetIcon(p.icon, `${p.name || "Pattern"} icon`, ICON_FALLBACK.pattern);
            if (icon) head.appendChild(icon);
            const name = document.createElement("div");
            name.className = "pattern-name";
            name.textContent = p.name || "";
            head.appendChild(name);
            card.appendChild(head);

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
            return card;
        }

        const outer = document.createElement("div");
        outer.className = "intro-grouped-list";
        for (const group of groupedIntroItems(patterns, "Patterns")) {
            const section = document.createElement("section");
            section.className = "intro-item-group";
            const title = document.createElement("h3");
            title.className = "intro-item-group-title";
            title.textContent = group.name;
            section.appendChild(title);

            const grid = document.createElement("div");
            grid.className = "patterns-list";
            group.items.forEach((p) => grid.appendChild(makePatternCard(p)));
            section.appendChild(grid);
            outer.appendChild(section);
        }

        return outer;
    }

    // Overview > Concepts. Deduped from step.concepts and linked to the steps
    // where each concept appears.
    function renderIntroConcepts(items) {
        return renderTopConcepts(items, {
            className: "overview-concepts",
            grouped: true,
            showSteps: true,
            showTitle: false,
        });
    }

    // Pattern Catalog (catalog dataset). Each item: { name, category?, what,
    // whenToUse?, tradeoffs?, usedBy? }. A standalone reference of the reusable
    // patterns the book teaches; cases reference these by name. Groups cards by
    // `category`/`group` when present.
    function renderIntroPatternCatalog(items) {
        const outer = document.createElement("div");

        // Group items by category/group (preserving first-seen order); ungrouped last.
        const order = [];
        const byCat = new Map();
        for (const p of items) {
            const cat = p.category || p.group || "";
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

                const head = document.createElement("div");
                head.className = "asset-heading pattern-heading";
                const icon = makeAssetIcon(p.icon, `${p.name || "Pattern"} icon`);
                if (icon) head.appendChild(icon);
                const name = document.createElement("div");
                name.className = "pattern-name";
                name.textContent = p.name || "";
                head.appendChild(name);
                card.appendChild(head);

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

    // Overview > Interview Script. Each item: { phase, time?, say }.
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
            case INTRO_SLUGS.concepts:
                node = renderIntroConcepts(entry.payload);
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
            case INTRO_SLUGS.toProbeFurther:
                node = renderIntroToProbeFurther(entry.payload);
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
        renderDescription(step.description, step.whyNow, step.decisionPrompt);

        if (Array.isArray(step.options) && step.options.length > 0) {
            if (state.currentOptionIndex >= step.options.length) state.currentOptionIndex = 0;
        } else {
            state.currentOptionIndex = 0;
        }

        els.introBlock.hidden = true;
        els.diagramBlock.hidden = false;
        renderDiagramViewTabs(entry);
        renderOptionTabs(step);
        renderOptionDescription(step);
        renderProsCons(step);
        const focus = effectiveDiagramFor(step);
        let diagram = focus.diagram;
        let highlight = focus.highlight;
        let diagramPrevStep = prevStep;
        if (entry.kind === "step" && state.currentDiagramView === "context") {
            // Full context = the final-design architecture, with this step's
            // focus nodes highlighted so the reader sees where it fits.
            diagram = fullContextDiagramFor(state.currentEntryIndex, focus.diagram);
            highlight = fullContextHighlightFor(step, diagram);
            diagramPrevStep = null;
        }
        await renderDiagram(diagram, highlight, diagramPrevStep);

        renderStepExtras(step);
        if (entry.id === INTRO_SLUGS.finalDesign) {
            appendStepExtra(renderGeneratedImage(step.image, `${step.title || "Final Design"} generated image`));
        }
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
            (f) => hasFlowDiagram(f)
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
        function validateDiagramArray(value, label) {
            if (value !== undefined && !Array.isArray(value)) {
                throw new Error(`${label}: Mermaid diagram fields must be arrays of source lines`);
            }
        }
        function validateAssetPath(value, label) {
            if (value !== undefined && typeof value !== "string") {
                throw new Error(`${label}: asset path must be a string`);
            }
        }
        function validateOptionalString(value, label) {
            if (value !== undefined && typeof value !== "string") {
                throw new Error(`${label}: must be a string if present`);
            }
        }
        validateDiagramArray(d.requirementsDiagram, `Dataset ${path} requirementsDiagram`);
        validateDiagramArray(d.capacityDiagram, `Dataset ${path} capacityDiagram`);
        validateDiagramArray(d.dataModelDiagram, `Dataset ${path} dataModelDiagram`);
        if (d.assets !== undefined) {
            if (!d.assets || typeof d.assets !== "object" || Array.isArray(d.assets)) {
                throw new Error(`Dataset ${path}: "assets" must be an object if present`);
            }
            for (const key of ["icon"]) {
                validateAssetPath(d.assets[key], `Dataset ${path} assets.${key}`);
            }
            for (const key of ["requirements", "capacityEstimation", "apiDesign"]) {
                if (d.assets[key] !== undefined) {
                    throw new Error(`Dataset ${path}: assets.${key} is not supported; generated images are only rendered for finalDesign.image`);
                }
            }
        }
        const knownProbeLinks = new Set();
        if (d.toProbeFurther !== undefined) {
            const validContainer = Array.isArray(d.toProbeFurther) ||
                (d.toProbeFurther && typeof d.toProbeFurther === "object");
            if (!validContainer) {
                throw new Error(`Dataset ${path}: "toProbeFurther" must be an object or array if present`);
            }
            const links = probeFurtherLinks(d.toProbeFurther);
            links.forEach((link, i) => {
                const id = String(link.id || "").trim();
                if (!id) {
                    throw new Error(`Dataset ${path}: toProbeFurther link ${i} must define a non-empty id`);
                }
                if (knownProbeLinks.has(id)) {
                    throw new Error(`Dataset ${path}: duplicate toProbeFurther link id "${id}"`);
                }
                knownProbeLinks.add(id);
                if (typeof link.title !== "string" || !link.title.trim()) {
                    throw new Error(`Dataset ${path}: toProbeFurther link "${id}" title must be a non-empty string`);
                }
                if (typeof link.url !== "string" || !/^https?:\/\//i.test(link.url.trim())) {
                    throw new Error(`Dataset ${path}: toProbeFurther link "${id}" url must be an http(s) URL`);
                }
            });
        }
        (d.steps || []).forEach((step, i) => {
            if (!step || typeof step !== "object") throw new Error(`Step ${i} is not an object`);
            if (step.diagram !== undefined) throw new Error(`Step ${i} ("${step.title || step.id || ""}") must use "view", not "diagram"`);
            if (step.image !== undefined) {
                throw new Error(`Step ${i} ("${step.title || step.id || ""}"): generated images are only supported for finalDesign.image`);
            }
            if (step.probeLinks !== undefined) {
                if (!Array.isArray(step.probeLinks)) {
                    throw new Error(`Step ${i} ("${step.title || step.id || ""}"): "probeLinks" must be an array`);
                }
                step.probeLinks.forEach((id, j) => {
                    const normalized = String(id || "").trim();
                    if (!normalized) {
                        throw new Error(`Step ${i} ("${step.title || step.id || ""}"): probeLinks[${j}] must be a non-empty string`);
                    }
                    if (!knownProbeLinks.has(normalized)) {
                        throw new Error(`Step ${i} ("${step.title || step.id || ""}"): probeLinks[${j}] references unknown link id "${normalized}"`);
                    }
                });
            }
            (Array.isArray(step.concepts) ? step.concepts : []).forEach((concept, j) => {
                if (concept && typeof concept === "object") {
                    validateAssetPath(concept.icon, `Step ${i} concept ${j} icon`);
                    validateOptionalString(concept.group, `Step ${i} concept ${j} group`);
                }
            });
            (step.options || []).forEach((opt, j) => {
                if (opt.diagram !== undefined) throw new Error(`Step ${i} option ${j} ("${opt.name || ""}") must use "view", not "diagram"`);
            });
            (step.deepDives || []).forEach((dd, j) => {
                if (dd && typeof dd === "object") {
                    if (dd.diagram !== undefined) throw new Error(`Step ${i} deepDive ${j} ("${dd.title || ""}") must use "view", not "diagram"`);
                }
            });
            if (!hasStepLikeDiagram(step)) {
                throw new Error(`Step ${i} ("${step.title || step.id || ""}") must define a "view" or non-empty "options[]" with views`);
            }
        });
        if (d.finalDesign) {
            if (d.finalDesign.diagram !== undefined) throw new Error(`Dataset ${path}: finalDesign must use "view", not "diagram"`);
            validateAssetPath(d.finalDesign.image, `Dataset ${path}: finalDesign.image`);
            (d.finalDesign.options || []).forEach((opt, j) => {
                if (opt.diagram !== undefined) throw new Error(`Dataset ${path}: finalDesign option ${j} must use "view", not "diagram"`);
            });
        }
        if (d.finalDesign && !hasStepLikeDiagram(d.finalDesign)) {
            throw new Error(`Dataset ${path}: "finalDesign" must define a "view" or non-empty "options[]" with views`);
        }
        // Book-feature fields are optional, but if present must be arrays so the
        // renderers can iterate them. Contents stay free-form (rendered only if
        // present), matching the rest of the lenient schema.
        for (const key of ["patterns", "interviewScript", "levelVariants", "patternCatalog"]) {
            if (d[key] !== undefined && !Array.isArray(d[key])) {
                throw new Error(`Dataset ${path}: "${key}" must be an array if present`);
            }
        }
        (d.patterns || []).forEach((pattern, i) => {
            if (pattern && typeof pattern === "object") {
                validateAssetPath(pattern.icon, `Dataset ${path}: patterns[${i}].icon`);
                validateOptionalString(pattern.group, `Dataset ${path}: patterns[${i}].group`);
            }
        });
        (d.patternCatalog || []).forEach((pattern, i) => {
            if (pattern && typeof pattern === "object") {
                validateAssetPath(pattern.icon, `Dataset ${path}: patternCatalog[${i}].icon`);
                validateOptionalString(pattern.group, `Dataset ${path}: patternCatalog[${i}].group`);
            }
        });
        const architecture = d.highLevelArchitecture;
        if (!architecture || typeof architecture !== "object") {
            throw new Error(`Dataset ${path}: "highLevelArchitecture" must be an object`);
        }
        if (!Array.isArray(architecture.nodes)) {
            throw new Error(`Dataset ${path}: highLevelArchitecture.nodes must be an array`);
        }
        if (!Array.isArray(architecture.links)) {
            throw new Error(`Dataset ${path}: highLevelArchitecture.links must be an array`);
        }
        if (!Array.isArray(architecture.types)) {
            throw new Error(`Dataset ${path}: highLevelArchitecture.types must be an array`);
        }
        architecture.nodes.forEach((node, i) => {
            if (!node || typeof node !== "object") {
                throw new Error(`Dataset ${path}: highLevelArchitecture.nodes[${i}] is not an object`);
            }
            if (!node.id || !node.type || !node.category || !Array.isArray(node.traits)) {
                throw new Error(`Dataset ${path}: highLevelArchitecture.nodes[${i}] needs id, type, category, and traits[]`);
            }
        });
        (architecture.links || []).forEach((link, i) => {
            if (!link || typeof link !== "object" || !link.id || !link.from || !link.to) {
                throw new Error(`Dataset ${path}: highLevelArchitecture.links[${i}] needs id, from, and to`);
            }
        });
        (architecture.types || []).forEach((type, i) => {
            if (!type || typeof type !== "object" || !type.id || !Array.isArray(type.nodes)) {
                throw new Error(`Dataset ${path}: highLevelArchitecture.types[${i}] needs id and nodes[]`);
            }
        });
        const linkIds = new Set((architecture.links || []).map((l) => l.id));
        const groupIds = new Set((architecture.types || []).map((g) => g.id));
        function validateView(view, label) {
            if (!view) return;
            if (!hasGraphView(view)) throw new Error(`${label}: "view" must define nodes[], links[], groups[], or mode`);
            if (view.nodes !== undefined && !Array.isArray(view.nodes)) throw new Error(`${label}: view.nodes must be an array`);
            if (view.links !== undefined && !Array.isArray(view.links)) throw new Error(`${label}: view.links must be an array`);
            if (view.groups !== undefined && !Array.isArray(view.groups)) throw new Error(`${label}: view.groups must be an array`);
            (view.links || []).forEach((ref) => {
                if (typeof ref === "string" && !linkIds.has(ref)) throw new Error(`${label}: view.links references unknown link "${ref}"`);
            });
            (view.groups || []).forEach((ref) => {
                const id = typeof ref === "string" ? ref : ref && ref.id;
                if (id && !groupIds.has(id)) throw new Error(`${label}: view.groups references unknown high-level architecture type "${id}"`);
            });
        }
        function validateSequence(sequence, label) {
            if (!sequence) return;
            if (!hasSequence(sequence)) throw new Error(`${label}: "sequence" must define participants[] and messages[]`);
            sequence.participants.forEach((participant, j) => {
                const normalized = normalizeSequenceParticipant(participant);
                if (!normalized.id) throw new Error(`${label}: sequence.participants[${j}] needs an id`);
            });
            function validateMessages(messages, pathLabel) {
                messages.forEach((message, j) => {
                    if (!message || typeof message !== "object") throw new Error(`${pathLabel}[${j}] is not an object`);
                    const type = String(message.type || "").trim().toLowerCase();
                    if (message.from !== undefined || message.to !== undefined) {
                        if (!message.from || !message.to) throw new Error(`${pathLabel}[${j}] needs from and to`);
                    }
                    if (Array.isArray(message.messages)) validateMessages(message.messages, `${pathLabel}[${j}].messages`);
                    if (message.else && typeof message.else === "object" && Array.isArray(message.else.messages)) {
                        validateMessages(message.else.messages, `${pathLabel}[${j}].else.messages`);
                    }
                    if (type === "par" && Array.isArray(message.branches)) {
                        message.branches.forEach((branch, k) => {
                            if (branch && Array.isArray(branch.messages)) validateMessages(branch.messages, `${pathLabel}[${j}].branches[${k}].messages`);
                        });
                    }
                });
            }
            validateMessages(sequence.messages, `${label}: sequence.messages`);
        }
        function validateFlow(flow, label) {
            if (!flow || typeof flow !== "object") throw new Error(`${label}: flow is not an object`);
            if (flow.diagram !== undefined) throw new Error(`${label}: use "sequence"; Mermaid "diagram" is not supported for flows`);
            if (!hasSequence(flow.sequence)) throw new Error(`${label}: flow must define a structured "sequence"`);
            validateSequence(flow.sequence, label);
        }
        (d.steps || []).forEach((step, i) => {
            validateView(step.view, `Step ${i} ("${step.title || step.id || ""}")`);
            (step.options || []).forEach((opt, j) => validateView(opt.view, `Step ${i} option ${j} ("${opt.name || ""}")`));
            (step.deepDives || []).forEach((dd, j) => {
                if (dd && typeof dd === "object") validateView(dd.view, `Step ${i} deepDive ${j} ("${dd.title || ""}")`);
            });
            if (step.flows !== undefined && !Array.isArray(step.flows)) throw new Error(`Step ${i} ("${step.title || step.id || ""}"): "flows" must be an array if present`);
            (step.flows || []).forEach((flow, j) => validateFlow(flow, `Step ${i} flow ${j} ("${flow && flow.name || ""}")`));
        });
        (Array.isArray(d.api) ? d.api : []).forEach((row, i) => {
            if (row && row.diagram !== undefined) throw new Error(`API row ${i} ("${row.method || ""} ${row.path || ""}"): use "sequence"; Mermaid "diagram" is not supported for flows`);
            validateSequence(row && row.sequence, `API row ${i} ("${row && row.method || ""} ${row && row.path || ""}")`);
        });
        if (d.finalDesign) {
            validateView(d.finalDesign.view, `Dataset ${path} finalDesign`);
            (d.finalDesign.options || []).forEach((opt, j) => validateView(opt.view, `Dataset ${path} finalDesign option ${j}`));
            if (d.finalDesign.flows !== undefined && !Array.isArray(d.finalDesign.flows)) throw new Error(`Dataset ${path} finalDesign: "flows" must be an array if present`);
            (d.finalDesign.flows || []).forEach((flow, j) => validateFlow(flow, `Dataset ${path} finalDesign flow ${j} ("${flow && flow.name || ""}")`));
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
            state.currentDatasetPath = meta.path;
            state.data = data;
            state.nodeIndex = buildNodeIndex(data);
            state.linkIndex = buildLinkIndex(data);
            state.architectureTypeIndex = buildArchitectureTypeIndex(data);
            state.entries = buildEntries(data);

            els.datasetTitle.textContent = data.title || meta.name || "System Design Explorer";

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

    // Returns { groups, datasets } where `datasets` is the flat list and each
    // dataset carries its resolved `groupId` / `groupName`.
    function normalizeManifest(manifest) {
        const groups = manifest && Array.isArray(manifest.groups)
            ? manifest.groups
                .filter((g) => g && Array.isArray(g.datasets))
                .map((g) => ({
                    id: g.id || g.name || "group",
                    name: g.name || g.id || "Group",
                    datasets: g.datasets,
                }))
            : [];
        const datasets = [];
        groups.forEach((g) => {
            g.datasets.forEach((d) => {
                datasets.push(Object.assign({groupId: g.id, groupName: g.name}, d));
            });
        });
        return {groups, datasets};
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
                throw new Error('data/index.json must contain a non-empty "groups" array');
            }
            state.groups = groups;
            state.datasets = datasets;
            state.nodeTypeConfig = await loadNodeTypeConfig();
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
