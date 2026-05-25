#!/usr/bin/env python3
"""Builder template for a new interview dataset.

Copy this to `data/<group>/<id>/_build.py`, fill in the catalog + steps below,
run `python3 data/<group>/<id>/_build.py`, then DELETE the copy (builder
helpers are temporary and never shipped). It writes `interview.json` next to
itself. The example content is a minimal URL-shortener so the template runs
as-is; replace it with your system.

Conventions (see ../reference.md for the full schema):
- NODES / LINKS define the highLevelArchitecture catalog ONCE; views and the
  final design reference their ids, so everything stays consistent.
- Step 1 must be a genuine naive baseline.
- Add flows to the 2-3 most interaction-heavy steps.
- Write labels as plain text; the renderer escapes Mermaid special chars.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- Node catalog: id -> (label, type, category, traits, description) -------
# type: actor|client|edge|gateway|service|orchestrator|worker|queue|stream|
#       cache|database|object-storage|index|model|observability|external
# category: boundary|traffic|compute|async|state|ops
NODES = {
    "Client": ("Client", "client", "boundary", [], "User's app; creates and resolves short links."),
    "LB":     ("Load Balancer", "edge", "traffic", ["stateless"], "Terminates TLS and spreads requests."),
    "App":    ("Link Service", "service", "compute", ["stateless"], "Creates short codes and resolves redirects."),
    "DB":     ("Mapping Store", "database", "state", ["stateful"], "Authoritative short_code -> long_url mapping."),
    "Cache":  ("Redirect Cache", "cache", "state", ["stateful", "derived"], "Hot short_code -> long_url for fast redirects."),
}

# ---- Link catalog: id -> (from, to, label) ----------------------------------
LINKS = {
    "client-lb":  ("Client", "LB", "HTTPS"),
    "lb-app":     ("LB", "App", "route"),
    "app-db":     ("App", "DB", "read/write mapping"),
    "app-cache":  ("App", "Cache", "read hot code"),
    "cache-db":   ("Cache", "DB", "miss -> load"),
}

# Optional subgraph groups: id -> (label, [node ids]). Leave empty list if none.
TYPES = [
    # {"id": "read-path", "label": "Read Path", "nodes": ["Client", "App", "Cache", "DB"]},
]


# ---------------------------------------------------------------------------
def view(nodes, links, highlight=None, groups=None):
    v = {"nodes": list(nodes), "links": list(links)}
    if highlight:
        v["highlight"] = list(highlight)
    if groups:
        v["groups"] = list(groups)
    return v


def hla():
    nodes = [{"id": n, "label": l, "type": t, "category": c, "traits": tr, "description": d}
             for n, (l, t, c, tr, d) in NODES.items()]
    links = [{"id": i, "from": f, "to": to, "label": lb} for i, (f, to, lb) in LINKS.items()]
    return {"nodes": nodes, "links": links, "types": list(TYPES)}


def seq(parts, msgs, highlight=None):
    """A flow: parts=[{'id':..,'label'?:..}], msgs=[{from,to,arrow,label}] (alt/else allowed)."""
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight:
        out["highlight"] = highlight
    return out


# ---- The dataset ------------------------------------------------------------
data = {
    "title": "URL Shortener — System Design",
    "description": "Design a service that turns long URLs into short codes and redirects on lookup. The themes are id/code generation, a read-heavy redirect path, and caching.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  User[User]", "  Shorten[Shorten URL]", "  Redirect[Resolve short code]",
        "  User --> Shorten", "  User --> Redirect",
    ],
    "capacityDiagram": [
        "graph LR",
        "  W[Writes ~1K/s]", "  R[Redirects ~100K/s]", "  W --> R",
    ],

    "requirements": {
        "functional": [
            "Create a short code for a long URL.",
            "Redirect a short code to its long URL.",
        ],
        "nonFunctional": [
            "Read-heavy: redirects vastly outnumber creates.",
            "Redirect latency p99 low; highly available.",
        ],
    },
    "capacity": [
        {"label": "Redirects/sec", "value": "~100,000", "note": "100:1 read/write"},
    ],
    "api": [
        {"method": "POST", "path": "/v1/shorten",
         "description": "Create a short code.",
         "request": "{ \"longUrl\": \"...\" }", "response": "{ \"shortUrl\": \"...\" }"},
        {"method": "GET", "path": "/{code}",
         "description": "Redirect to the long URL.",
         "request": "(code in path)", "response": "302 -> long URL"},
    ],
    "dataModel": [
        {"name": "urls", "note": "Primary mapping.",
         "fields": [{"name": "short_code", "type": "varchar(10) PK"},
                    {"name": "long_url", "type": "text"}]},
    ],
    "patterns": [
        {"name": "Cache-aside", "what": "Check cache, load DB on miss, backfill.",
         "whenToUse": "Read-heavy lookups.", "steps": ["cache"]},
    ],

    "steps": [
        {
            "id": "naive",
            "title": "1. Naive: One Service, One Table (the baseline)",
            "description": [
                "Start with the simplest thing that works: a single service writes (short_code, long_url) to one database on create, and reads it back on redirect.",
                "It's correct, and it exposes the bottleneck: at 100K redirects/sec every lookup hits the database, which won't keep up — motivating a cache on the read path.",
            ],
            "view": view(["Client", "LB", "App", "DB"], ["client-lb", "lb-app", "app-db"], highlight=["App", "DB"]),
            "decisionPrompt": "What happens to the database at 100K redirects/sec if every redirect is a DB read?",
            "whyNow": ["The naive baseline makes the read-heavy bottleneck obvious before adding a cache."],
            "recap": {"before": "Nothing.", "after": "Creates and redirects work against one DB.",
                      "newRisk": "Every redirect hits the DB — it melts under read load."},
            "traps": [{"trap": "Serving redirects straight from the DB at scale.",
                       "why": "Redirects are ~100x writes; the DB can't sustain that read rate.",
                       "instead": "Cache hot codes on the read path."}],
        },
        {
            "id": "cache",
            "title": "2. Cache the Redirect Path",
            "description": [
                "Put a cache in front of the mapping store: redirects read the cache first and fall back to the DB on a miss, backfilling the cache (cache-aside).",
                "Now the hot working set is served from memory, and the DB only sees misses and writes.",
            ],
            "view": view(["Client", "App", "Cache", "DB"], ["lb-app", "app-cache", "cache-db", "app-db"], highlight=["Cache"]),
            "decisionPrompt": "On a cache miss, who loads from the DB and backfills?",
            "patterns": ["Cache-aside"],
            "concepts": [{"term": "Cache-aside",
                          "definition": "App checks cache, reads DB on miss, then backfills the cache.",
                          "whyItMatters": "Simple and resilient; a cache outage just means more DB load.",
                          "example": "GET /{code} -> miss -> SELECT -> SET code."}],
            "whyNow": ["Caching is the direct fix for the read-heavy bottleneck from step 1."],
            "flows": [
                seq([{"id": "Client"}, {"id": "Cache", "label": "Redirect Cache"}, {"id": "DB", "label": "Mapping Store"}],
                    [{"from": "Client", "to": "Cache", "arrow": "->>", "label": "GET code"},
                     {"type": "alt", "label": "miss",
                      "messages": [{"from": "Cache", "to": "DB", "arrow": "->>", "label": "load"},
                                   {"from": "DB", "to": "Cache", "arrow": "-->>", "label": "long URL"}],
                      "else": {"label": "hit",
                               "messages": [{"from": "Cache", "to": "Client", "arrow": "-->>", "label": "redirect"}]}}],
                    highlight=["Cache"]),
            ],
            "recap": {"before": "Every redirect hit the DB.", "after": "Hot redirects served from cache.",
                      "newRisk": "Cache invalidation / cold cache on restart (next steps)."},
        },
        # ... add more steps: id generation, scaling, etc. Aim for 5-7 total.
    ],

    "finalDesign": {
        "title": "Final Design — URL Shortener",
        "description": "Clients create codes via the link service (DB write); redirects read the cache, falling back to the DB on a miss and backfilling.",
        "view": view(["Client", "LB", "App", "Cache", "DB"],
                     ["client-lb", "lb-app", "app-db", "app-cache", "cache-db"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "Create a short code", "how": "Link service writes the mapping.", "steps": ["naive"]},
            {"requirement": "Redirect", "how": "Cache-aside read of the mapping.", "steps": ["cache"]},
        ],
        "nonFunctional": [
            {"requirement": "Read-heavy / low latency", "how": "Hot codes served from cache.", "steps": ["cache"]},
        ],
    },
    "interviewScript": [
        {"phase": "Scope", "time": "first 5 min", "say": ["Confirm read-heavy redirects dominate creates."]},
        {"phase": "Design", "time": "next 10 min", "say": ["Naive single-DB design, then cache the read path."]},
    ],
    "levelVariants": [
        {"level": "Junior", "expectations": ["Stores the mapping and redirects.", "Adds a cache."]},
        {"level": "Senior", "expectations": ["Cache-aside; reasons about id generation and scaling."]},
    ],
    "followUps": [
        "How do you generate unique short codes (counter vs hash vs base62)?",
        "How do you handle custom aliases and expiry?",
    ],
}


if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
