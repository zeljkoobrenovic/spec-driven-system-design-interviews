#!/usr/bin/env python3
"""Builder for the ML Feature Store book case."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

NODES = {
    "Author":    ("ML Engineer", "actor", "boundary", [], "Defines feature transformations once; uses them in training and serving."),
    "Registry":  ("Feature Registry", "service", "compute", ["stateful"], "Central definitions: each feature's name, source, transform, owner."),
    "Batch":     ("Batch Compute (Offline)", "worker", "async", ["stateless"], "Computes features over historical data on a schedule."),
    "Stream":    ("Stream Compute (Online)", "worker", "async", ["stateless"], "Computes fresh features from event streams in near-real-time."),
    "Sources":   ("Data Sources", "external", "boundary", [], "Warehouses, event streams, and operational DBs feature inputs come from."),
    "Offline":   ("Offline Store (Warehouse)", "database", "state", ["stateful"], "Historical feature values with timestamps for training."),
    "Online":    ("Online Store (Low-Latency)", "cache", "state", ["stateful", "derived"], "Latest feature values keyed by entity for serving."),
    "TrainAPI":  ("Training Data API", "service", "compute", ["stateless"], "Builds point-in-time-correct training datasets from the offline store."),
    "ServeAPI":  ("Online Serving API", "service", "compute", ["stateless"], "Returns features for an entity at inference time (ms)."),
    "Model":     ("Model / Inference Service", "model", "compute", ["stateless"], "Consumes features online; trained on offline features."),
    "Materializer": ("Materialization Job", "worker", "async", ["stateless"], "Loads computed features into the online store; keeps it fresh."),
    "Monitor":   ("Monitoring / Drift", "observability", "ops", ["stateful"], "Tracks freshness, drift, and serving/training skew."),
}

LINKS = {
    "author-registry":  ("Author", "Registry", "define feature"),
    "registry-batch":   ("Registry", "Batch", "transform spec"),
    "registry-stream":  ("Registry", "Stream", "transform spec"),
    "sources-batch":    ("Sources", "Batch", "historical data"),
    "sources-stream":   ("Sources", "Stream", "event stream"),
    "batch-offline":    ("Batch", "Offline", "write historical features"),
    "stream-online":    ("Stream", "Online", "write fresh features"),
    "batch-materializer": ("Batch", "Materializer", "materialize to online"),
    "materializer-online": ("Materializer", "Online", "load latest"),
    "train-offline":    ("TrainAPI", "Offline", "point-in-time join"),
    "model-train":      ("Model", "TrainAPI", "training dataset"),
    "model-serve":      ("Model", "ServeAPI", "fetch features (inference)"),
    "serve-online":     ("ServeAPI", "Online", "read latest features"),
    "monitor-online":   ("Monitor", "Online", "freshness / drift"),
    "monitor-offline":  ("Monitor", "Offline", "skew checks"),
}


def view(nodes, links, highlight=None, groups=None):
    v = {"nodes": list(nodes), "links": list(links)}
    if highlight: v["highlight"] = list(highlight)
    if groups: v["groups"] = list(groups)
    return v


def hla():
    nodes = [{"id": n, "label": l, "type": t, "category": c, "traits": tr, "description": d}
             for n, (l, t, c, tr, d) in NODES.items()]
    links = [{"id": i, "from": f, "to": to, "label": lb} for i, (f, to, lb) in LINKS.items()]
    types = [
        {"id": "define", "label": "Definition & Compute", "nodes": ["Registry", "Batch", "Stream", "Sources"]},
        {"id": "stores", "label": "Stores", "nodes": ["Offline", "Online", "Materializer"]},
        {"id": "consume", "label": "Train & Serve", "nodes": ["TrainAPI", "ServeAPI", "Model", "Monitor"]},
    ]
    return {"nodes": nodes, "links": links, "types": types}


def seq(parts, msgs, highlight=None):
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight: out["highlight"] = highlight
    return out


data = {
    "title": "ML Feature Store — System Design",
    "description": "Design a feature store: the central system that computes ML features once and serves them consistently for both training (offline, historical) and inference (online, low-latency). The themes are the offline/online dual store, point-in-time-correct training data, train/serve consistency, and feature freshness.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  Define[Define feature once]",
        "  Offline[Offline for training]",
        "  Online[Online for serving]",
        "  Consistent[Same definition both]",
        "  Fresh[Fresh online]",
        "  Define --> Offline",
        "  Define --> Online",
        "  Offline --> Consistent",
        "  Online --> Fresh",
    ],
    "capacityDiagram": [
        "graph LR",
        "  Features[1000s of features]",
        "  Train[Bulk historical reads]",
        "  Serve[ms online reads]",
        "  Features --> Train",
        "  Features --> Serve",
    ],

    "requirements": {
        "functional": [
            "Define a feature (source + transformation) once, in a central registry.",
            "Serve features online at inference time with low latency, keyed by entity.",
            "Provide historical feature values for training, joined correctly to labels.",
            "Compute features in batch (historical) and streaming (fresh).",
            "Reuse and share features across teams/models; discover them.",
        ],
        "nonFunctional": [
            "Train/serve consistency: training and serving use the same feature definitions/values logic (no skew).",
            "Point-in-time correctness: training data uses feature values as of each event's time (no leakage).",
            "Low online serving latency (single-digit ms) under high QPS.",
            "Freshness: online features reflect recent data within an acceptable lag.",
            "Scale to thousands of features across many entities and models.",
        ],
    },

    "capacity": [
        {"label": "Features", "value": "1000s", "note": "Shared across many models/teams."},
        {"label": "Online reads", "value": "ms, high QPS", "note": "On the inference critical path."},
        {"label": "Offline reads", "value": "bulk", "note": "Large historical joins for training."},
        {"label": "Freshness", "value": "seconds-minutes", "note": "Streaming features fresher than batch."},
        {"label": "Skew tolerance", "value": "zero (logic)", "note": "Same transform offline and online."},
    ],

    "api": [
        {"method": "POST", "path": "/v1/features",
         "description": "Register a feature definition (source + transform) used by both training and serving.",
         "request": "{ \"name\": \"user_7d_clicks\", \"entity\": \"user\", \"source\": \"clicks\", \"transform\": \"count_7d\" }",
         "response": "{ \"featureId\": \"f_9\" }",
         **seq(
             [{"id": "Author"}, {"id": "Registry", "label": "Feature Registry"}, {"id": "Batch", "label": "Batch Compute"}, {"id": "Stream", "label": "Stream Compute"}],
             [
                 {"from": "Author", "to": "Registry", "arrow": "->>", "label": "define feature"},
                 {"from": "Registry", "to": "Batch", "arrow": "->>", "label": "offline transform spec"},
                 {"from": "Registry", "to": "Stream", "arrow": "->>", "label": "online transform spec (same logic)"},
                 {"from": "Registry", "to": "Author", "arrow": "-->>", "label": "registered"},
             ])},
        {"method": "GET", "path": "/v1/online-features",
         "description": "Fetch latest feature values for an entity at inference time.",
         "request": "?entity=user&id=u_42&features=user_7d_clicks,user_country",
         "response": "{ \"user_7d_clicks\": 14, \"user_country\": \"US\" }",
         **seq(
             [{"id": "Model"}, {"id": "ServeAPI", "label": "Online Serving"}, {"id": "Online", "label": "Online Store"}],
             [
                 {"from": "Model", "to": "ServeAPI", "arrow": "->>", "label": "get features(u_42)"},
                 {"from": "ServeAPI", "to": "Online", "arrow": "->>", "label": "read latest by entity"},
                 {"from": "ServeAPI", "to": "Model", "arrow": "-->>", "label": "feature vector"},
             ])},
        {"method": "POST", "path": "/v1/training-data",
         "description": "Build a point-in-time-correct training dataset from an entity+timestamp list.",
         "request": "{ \"entities\": [ {entity, ts, label} ... ], \"features\": [...] }",
         "response": "{ \"datasetUri\": \"...\" }",
         **seq(
             [{"id": "Model"}, {"id": "TrainAPI", "label": "Training Data API"}, {"id": "Offline", "label": "Offline Store"}],
             [
                 {"from": "Model", "to": "TrainAPI", "arrow": "->>", "label": "entities + timestamps + label"},
                 {"from": "TrainAPI", "to": "Offline", "arrow": "->>", "label": "point-in-time join (as-of ts)"},
                 {"from": "TrainAPI", "to": "Model", "arrow": "-->>", "label": "training dataset"},
             ])},
    ],

    "dataModel": [
        {"name": "feature_definition", "note": "Central definition reused by offline + online compute.",
         "fields": [
             {"name": "feature_id", "type": "string PK"},
             {"name": "entity", "type": "string (user/item/...)"},
             {"name": "source", "type": "table/stream"},
             {"name": "transform", "type": "spec (aggregation, window)"},
             {"name": "owner / version", "type": "governance"},
         ]},
        {"name": "offline_feature (warehouse)", "note": "Timestamped historical values for point-in-time joins.",
         "fields": [
             {"name": "entity_id", "type": "..."},
             {"name": "feature_values", "type": "map"},
             {"name": "event_ts", "type": "when the value was valid"},
         ]},
        {"name": "online_feature (kv)", "note": "Latest value per entity for low-latency serving.",
         "fields": [
             {"name": "entity_id", "type": "key"},
             {"name": "feature_values", "type": "map (latest)"},
             {"name": "updated_at", "type": "freshness"},
         ]},
    ],

    "patterns": [
        {"name": "Central feature registry", "what": "Define each feature once with a source + transform; everything references the definition.",
         "whenToUse": "Sharing/governing features across teams and avoiding duplicate logic.", "steps": ["registry"]},
        {"name": "Dual offline/online stores", "what": "An offline store (historical, for training) and an online store (latest, for serving), fed from the same definitions.",
         "whenToUse": "Features needed for both bulk training and low-latency inference.", "steps": ["stores"]},
        {"name": "Point-in-time correctness", "what": "Join feature values as-of each training event's timestamp, never future values.",
         "whenToUse": "Building training data without label leakage.", "steps": ["training"]},
        {"name": "Train/serve consistency", "what": "Use identical feature logic offline and online so the model sees the same inputs.",
         "whenToUse": "Any production ML system (skew silently degrades quality).", "steps": ["serving"]},
        {"name": "Materialization + freshness", "what": "Materialize computed features into the online store; streaming for fresh, batch for the rest.",
         "whenToUse": "Keeping serving features current at acceptable cost.", "steps": ["freshness"]},
        {"name": "Feature monitoring (drift/skew)", "what": "Monitor freshness, distribution drift, and online/offline skew.",
         "whenToUse": "Detecting silent ML degradation.", "steps": ["freshness"]},
    ],

    "steps": [
        {
            "id": "registry",
            "title": "1. Define Features Once (Registry)",
            "description": [
                "The core idea: define each feature once — its entity, source data, and transformation (e.g. 'count of a user's clicks in the last 7 days') — in a central registry. Both the training and serving paths reference this single definition, so the logic can't diverge.",
                "Without this, teams reimplement the same feature differently in training pipelines and serving code — the classic source of train/serve skew. The registry also enables discovery and reuse (one team's feature is another's input) and governance (ownership, versioning).",
                "The definition is the contract; the rest of the system computes and serves it consistently.",
            ],
            "view": view(["Author", "Registry", "Batch", "Stream"],
                         ["author-registry", "registry-batch", "registry-stream"],
                         highlight=["Registry"], groups=["define"]),
            "decisionPrompt": "Why define features centrally instead of computing them inside each training pipeline and serving service?",
            "concepts": [
                {"term": "Feature registry", "definition": "A central catalog of feature definitions (source + transform) referenced everywhere.",
                 "whyItMatters": "Single source of truth prevents duplicated/divergent logic and enables reuse + governance.",
                 "example": "Define user_7d_clicks once; training and serving both use it."},
            ],
            "patterns": ["Central feature registry"],
            "whyNow": ["The registry is the foundation; defining features once is precisely what makes train/serve consistency achievable downstream."],
            "recap": {"before": "Nothing.", "after": "Features defined once, centrally, reusable.",
                      "newRisk": "Training needs bulk history; serving needs ms reads — one store can't do both well."},
        },
        {
            "id": "stores",
            "title": "2. Dual Offline and Online Stores",
            "description": [
                "Training and serving have opposite access patterns. Training reads large historical datasets (bulk, latency-tolerant); serving reads a few features for one entity in milliseconds. So maintain two stores fed from the same definitions.",
                "The offline store (a warehouse) holds timestamped historical feature values for building training data. The online store (a low-latency KV/cache) holds the latest value per entity for inference. Both are computed from the registry's definitions, so they're consistent by construction.",
                "This dual-store design is the architectural heart of a feature store: same feature, two materializations tuned to two very different read patterns.",
            ],
            "view": view(["Batch", "Offline", "Stream", "Online", "Sources"],
                         ["sources-batch", "batch-offline", "sources-stream", "stream-online"],
                         highlight=["Offline", "Online"], groups=["stores", "define"]),
            "decisionPrompt": "Why not serve training and inference from the same store?",
            "concepts": [
                {"term": "Offline/online dual store", "definition": "A historical store for training and a low-latency store for serving, from one definition.",
                 "whyItMatters": "Each is tuned to its access pattern while staying logically consistent.",
                 "example": "Warehouse holds 2 years of values; KV holds the latest per user for serving."},
            ],
            "patterns": ["Dual offline/online stores"],
            "whyNow": ["The dual store is the defining structure; everything (training correctness, serving latency, freshness) is shaped by it."],
            "recap": {"before": "One store.", "after": "Offline (historical) + online (latest), both from the registry.",
                      "newRisk": "Building training data naively from history can leak future information."},
        },
        {
            "id": "training",
            "title": "3. Point-in-Time-Correct Training Data",
            "description": [
                "Training joins features to labeled events. The trap: using a feature's current value for a past event leaks information the model wouldn't have had then (data leakage), inflating offline metrics and failing in production.",
                "Point-in-time correctness fixes this: for each training row (entity, event timestamp, label), join the feature value as it was at that timestamp — an 'as-of' join against the timestamped offline store. The training data API does this join correctly so engineers don't hand-roll it (and get it wrong).",
                "This is the subtlest correctness property of a feature store and a top interview signal: the offline store must be timestamped, and joins must respect those timestamps.",
            ],
            "view": view(["Model", "TrainAPI", "Offline"],
                         ["model-train", "train-offline"],
                         highlight=["TrainAPI", "Offline"], groups=["consume", "stores"]),
            "decisionPrompt": "You're training on an event from 3 months ago. Which value of 'user_7d_clicks' do you use?",
            "concepts": [
                {"term": "Point-in-time join", "definition": "Joining each training event to feature values as-of that event's timestamp.",
                 "whyItMatters": "Prevents label/feature leakage — the model trains on what it would have actually seen.",
                 "example": "Event at t -> user_7d_clicks as computed at t, not today's value."},
            ],
            "patterns": ["Point-in-time correctness"],
            "whyNow": ["Point-in-time correctness is the non-obvious correctness crux of training data; naming leakage and as-of joins is the staff-level signal."],
            "recap": {"before": "Leaky training joins.", "after": "Leakage-free, point-in-time-correct training data.",
                      "newRisk": "Serving must use the SAME feature logic, or online inputs differ from training (skew)."},
            "traps": [
                {"trap": "Joining current feature values to historical training events.", "why": "Leaks future information; offline metrics look great but production fails.",
                 "instead": "As-of (point-in-time) joins against timestamped feature values."},
            ],
        },
        {
            "id": "serving",
            "title": "4. Online Serving and Train/Serve Consistency",
            "description": [
                "At inference, the model fetches features for an entity from the online store via the serving API in single-digit ms. The critical correctness property: these online features must be computed by the same logic as the offline features used in training — otherwise train/serve skew silently degrades the model.",
                "The shared registry definition is what guarantees this: the same transform spec drives both offline (batch) and online (stream) computation, so 'user_7d_clicks' means the same thing in both. Avoid reimplementing the transform in serving code.",
                "Serving reads are simple key lookups (entity -> feature vector); the hard work (computing the features) happened upstream. Keep the online store in-memory/low-latency for the QPS.",
            ],
            "view": view(["Model", "ServeAPI", "Online"],
                         ["model-serve", "serve-online"],
                         highlight=["ServeAPI", "Online"], groups=["consume", "stores"]),
            "decisionPrompt": "How do you guarantee the 'user_7d_clicks' the model sees at serving equals what it was trained on?",
            "concepts": [
                {"term": "Train/serve consistency", "definition": "Identical feature logic (from one definition) used for both training and serving.",
                 "whyItMatters": "Eliminates skew — the silent killer of production ML quality.",
                 "example": "Same count_7d transform computes the offline and online value."},
            ],
            "patterns": ["Train/serve consistency"],
            "whyNow": ["Consistency is the whole point of a feature store; it's what the registry + dual store exist to deliver, and the most common ML-systems pitfall."],
            "recap": {"before": "Serving logic could diverge from training.", "after": "Identical logic both sides; low-latency serving.",
                      "newRisk": "Online features must be kept fresh, or serving uses stale values."},
        },
        {
            "id": "freshness",
            "title": "5. Materialization and Freshness",
            "description": [
                "The online store must reflect recent data. Materialize features into it: batch jobs refresh slowly-changing features on a schedule; stream processing updates fast-changing features (recent activity) in near-real-time from event streams.",
                "Freshness is per-feature: 'user lifetime purchases' can lag by hours; 'clicks in the last 5 minutes' must be seconds-fresh. The materialization layer picks batch vs stream per feature based on its freshness requirement, balancing cost against staleness.",
                "Monitoring closes the loop: track each feature's freshness, distribution drift over time, and online/offline skew (the served value vs what offline would compute) — catching silent degradation before it hurts the model.",
            ],
            "view": view(["Batch", "Materializer", "Online", "Stream", "Monitor"],
                         ["batch-materializer", "materializer-online", "stream-online", "monitor-online", "monitor-offline"],
                         highlight=["Materializer", "Monitor"], groups=["stores", "consume"]),
            "decisionPrompt": "Which features can be refreshed nightly in batch, and which must be updated within seconds?",
            "concepts": [
                {"term": "Per-feature materialization", "definition": "Batch for slow features, streaming for fast ones, loaded into the online store.",
                 "whyItMatters": "Meets each feature's freshness need without paying streaming cost for everything.",
                 "example": "Nightly batch for lifetime stats; streaming for last-5-min counts."},
                {"term": "Skew/drift monitoring", "definition": "Tracking freshness, distribution drift, and online-vs-offline value differences.",
                 "whyItMatters": "Detects silent ML degradation from stale/skewed features.",
                 "example": "Alert when online user_7d_clicks diverges from offline recompute."},
            ],
            "patterns": ["Materialization + freshness", "Feature monitoring (drift/skew)"],
            "whyNow": ["Freshness + monitoring make the online store trustworthy; per-feature materialization is the cost/freshness lever and the operational reality."],
            "recap": {"before": "Stale, unmonitored online features.", "after": "Per-feature fresh materialization + drift/skew monitoring.",
                      "newRisk": "Thousands of features, high serving QPS, and bulk training joins must all scale."},
        },
        {
            "id": "scale",
            "title": "6. Scale, Governance, and Reliability",
            "description": [
                "Scale the two stores independently: the online store (KV/in-memory) shards by entity for ms reads at high QPS; the offline store (warehouse/columnar) scales for bulk historical scans. Compute (batch + stream) scales with feature count and data volume.",
                "Governance matters at thousands of features: ownership, versioning (changing a feature's definition is a new version so models pin what they trained on), access control, and lineage (what sources/features feed a model). Reuse means a popular feature is computed once and serves many models.",
                "Reliability: the registry and offline store are authoritative; the online store and materialized values are derived and rebuildable (re-materialize from the offline store/sources). Serving degrades gracefully (default/last-known values) if a feature is missing, rather than failing inference.",
            ],
            "view": view(["Online", "Offline", "ServeAPI", "TrainAPI", "Registry"],
                         ["serve-online", "train-offline", "model-serve", "model-train"],
                         highlight=["Online", "Offline"], groups=["stores", "consume"]),
            "decisionPrompt": "An engineer changes a feature's definition. How do you avoid breaking models already trained on the old version?",
            "whyNow": ["Closing on scale + governance + reliability shows the feature store works across many teams/models and stays correct as definitions evolve."],
            "recap": {"before": "Functional feature store.", "after": "Independently-scaled stores, versioned/governed features, rebuildable online state.",
                      "newRisk": "Definition changes and materialization lag — bounded by feature versioning and rebuildable derived stores."},
            "bottlenecks": [
                {"issue": "Online serving QPS for hot entities.", "mitigation": "Shard online store by entity; cache hot keys; in-memory."},
                {"issue": "Definition change breaks pinned models.", "mitigation": "Version features; models pin versions; migrate deliberately."},
            ],
            "failureDrills": [
                {"scenario": "The online store loses a shard.",
                 "expectedBehavior": "Re-materialize features from the offline store/sources; serving falls back to defaults/last-known meanwhile.",
                 "mitigation": "Online store as rebuildable derived state + graceful serving fallback."},
            ],
        },
    ],

    "finalDesign": {
        "title": "Final Design — Feature Store",
        "description": "Engineers define each feature once in a central registry (source + transform). That single definition drives both batch (offline/historical) and stream (online/fresh) computation, written to a dual store: an offline warehouse of timestamped values and a low-latency online KV store of latest values. Training builds point-in-time-correct datasets via as-of joins on the offline store (no leakage); serving reads the online store in ms using the same feature logic (no train/serve skew). A materialization layer keeps the online store fresh per-feature (batch vs stream), and monitoring tracks freshness, drift, and skew. Stores scale independently and are governed/versioned; the online store is rebuildable derived state with graceful serving fallback.",
        "view": view(
            ["Author", "Registry", "Sources", "Batch", "Stream", "Offline", "Online", "Materializer",
             "TrainAPI", "ServeAPI", "Model", "Monitor"],
            ["author-registry", "registry-batch", "registry-stream", "sources-batch", "sources-stream",
             "batch-offline", "stream-online", "batch-materializer", "materializer-online", "train-offline",
             "model-train", "model-serve", "serve-online", "monitor-online", "monitor-offline"],
            groups=["define", "stores", "consume"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "Define feature once", "how": "Central feature registry.", "steps": ["registry"]},
            {"requirement": "Serve online (ms)", "how": "Online KV store + serving API.", "steps": ["serving"]},
            {"requirement": "Historical for training", "how": "Offline store + point-in-time join API.", "steps": ["stores", "training"]},
            {"requirement": "Batch + streaming compute", "how": "Same definition drives both; materialized.", "steps": ["stores", "freshness"]},
            {"requirement": "Reuse/discovery", "how": "Registry catalog + governance.", "steps": ["registry", "scale"]},
        ],
        "nonFunctional": [
            {"requirement": "Train/serve consistency", "how": "One definition -> both paths.", "steps": ["registry", "serving"]},
            {"requirement": "Point-in-time correctness", "how": "As-of joins on timestamped offline store.", "steps": ["training"]},
            {"requirement": "Low serving latency", "how": "Online KV/in-memory, sharded by entity.", "steps": ["serving", "scale"]},
            {"requirement": "Freshness", "how": "Per-feature batch/stream materialization + monitoring.", "steps": ["freshness"]},
            {"requirement": "Scale + governance", "how": "Independent store scaling + feature versioning.", "steps": ["scale"]},
        ],
    },

    "interviewScript": [
        {"phase": "Scope & requirements", "time": "first 5 min",
         "say": ["Confirm the goal: consistent features for both training and serving.",
                 "Pin train/serve consistency and point-in-time correctness as the hard goals.",
                 "Note low online latency vs bulk offline reads."]},
        {"phase": "High-level design", "time": "next 10 min",
         "say": ["Central registry: define each feature once.",
                 "Dual offline/online stores from the same definition.",
                 "Batch + stream compute feeding both."]},
        {"phase": "Deep dive", "time": "next 15 min",
         "say": ["Point-in-time-correct training joins (no leakage).",
                 "Online serving with identical logic (no skew).",
                 "Per-feature materialization/freshness + monitoring; scaling + versioning."]},
        {"phase": "Wrap-up", "time": "final 5 min",
         "say": ["Map requirements to mechanisms.",
                 "Tradeoffs: freshness vs cost, batch vs stream, definition-change versioning.",
                 "Mention lineage and feature reuse/governance as extensions."]},
    ],

    "levelVariants": [
        {"level": "Junior", "expectations": ["Serves features online and computes them for training.", "May reimplement logic per path (skew) and miss point-in-time."]},
        {"level": "Senior", "expectations": ["Central registry + dual stores.", "Point-in-time training joins.", "Per-feature freshness materialization."]},
        {"level": "Staff", "expectations": ["Reasons about train/serve skew and leakage precisely.", "Designs versioning/governance + rebuildable online store.", "Discusses batch-vs-stream freshness/cost and monitoring deeply."]},
    ],

    "followUps": [
        "How exactly does a point-in-time join avoid leakage, and what does the offline store need to support it?",
        "How do you detect and prevent train/serve skew in production?",
        "How do you decide batch vs streaming for a given feature?",
        "How do you version a feature whose definition changes, without breaking trained models?",
        "How would you support feature reuse and lineage across many teams?",
    ],
}

if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
