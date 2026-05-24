#!/usr/bin/env python3
"""Builder for the Distributed Cache book case (Memcached/Redis-style)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

NODES = {
    "App":      ("Application Service", "service", "compute", ["stateless"], "Reads through the cache; falls back to the database on a miss."),
    "ClientLib": ("Cache Client Library", "service", "compute", ["stateless"], "In-app library that hashes keys to shards and talks to cache nodes."),
    "Router":   ("Shard Router / Proxy", "service", "compute", ["stateless"], "Optional proxy that maps keys to cache nodes via consistent hashing."),
    "CacheA":   ("Cache Node A", "cache", "state", ["stateful", "derived"], "Holds a partition of the keyspace in memory."),
    "CacheB":   ("Cache Node B", "cache", "state", ["stateful", "derived"], "Holds another partition of the keyspace."),
    "CacheC":   ("Cache Node C", "cache", "state", ["stateful", "derived"], "Holds another partition of the keyspace."),
    "Replica":  ("Cache Replica", "cache", "state", ["stateful", "derived"], "Read replica / failover copy of a primary cache node."),
    "DB":       ("Backing Database", "database", "state", ["stateful"], "Authoritative source of truth behind the cache."),
    "Config":   ("Cluster Config / Membership", "service", "state", ["stateful"], "Tracks the ring topology and node health; clients refresh from it."),
    "Eviction": ("Eviction Manager", "worker", "compute", ["stateless"], "Per-node policy (LRU/LFU/TTL) reclaiming memory under pressure."),
}

LINKS = {
    "app-clientlib":    ("App", "ClientLib", "get/set key"),
    "clientlib-router": ("ClientLib", "Router", "route key"),
    "router-a":         ("Router", "CacheA", "key in range A"),
    "router-b":         ("Router", "CacheB", "key in range B"),
    "router-c":         ("Router", "CacheC", "key in range C"),
    "clientlib-a":      ("ClientLib", "CacheA", "direct (hash)"),
    "a-db":             ("CacheA", "DB", "miss -> load"),
    "app-db":           ("App", "DB", "read on miss / write"),
    "a-replica":        ("CacheA", "Replica", "replicate"),
    "replica-app":      ("Replica", "App", "serve on failover"),
    "config-clientlib": ("Config", "ClientLib", "ring + health"),
    "config-router":    ("Config", "Router", "ring + health"),
    "eviction-a":       ("Eviction", "CacheA", "evict under pressure"),
    "app-cachea":       ("App", "CacheA", "write-through"),
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
        {"id": "cache-tier", "label": "Cache Tier", "nodes": ["CacheA", "CacheB", "CacheC", "Replica"]},
        {"id": "control", "label": "Routing & Control", "nodes": ["ClientLib", "Router", "Config", "Eviction"]},
    ]
    return {"nodes": nodes, "links": links, "types": types}


def seq(parts, msgs, highlight=None):
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight: out["highlight"] = highlight
    return out


data = {
    "title": "Distributed Cache — System Design",
    "description": "Design an in-memory caching layer (Memcached/Redis-style) that sits in front of a database to absorb read load at low latency. The themes are sharding the keyspace, eviction policy, the cache/DB consistency model, and surviving hot keys and node failures.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  App[App]",
        "  Get[get key]",
        "  Hit[Cache hit -> fast]",
        "  Miss[Miss -> load from DB]",
        "  Scale[Add nodes -> more memory]",
        "  App --> Get",
        "  Get --> Hit",
        "  Get --> Miss",
        "  Miss --> Scale",
    ],
    "capacityDiagram": [
        "graph LR",
        "  RPS[~1M reads/s]",
        "  Hit[95%+ hit rate]",
        "  Mem[TBs of RAM]",
        "  RPS --> Hit",
        "  Hit --> Mem",
    ],

    "requirements": {
        "functional": [
            "get(key) and set(key, value, ttl); delete(key).",
            "Cache arbitrary serialized values keyed by string.",
            "Expire entries by TTL.",
            "Scale capacity by adding cache nodes.",
        ],
        "nonFunctional": [
            "Very low latency: sub-millisecond reads on a hit.",
            "High hit rate: absorb the vast majority of DB read load.",
            "Scale to ~1M+ ops/sec and terabytes of cached data.",
            "Tolerate cache-node failure without taking down the application.",
            "Bounded staleness: it's a cache, so some inconsistency with the DB is acceptable and must be reasoned about.",
        ],
    },

    "capacity": [
        {"label": "Reads per second", "value": "~1,000,000+", "note": "What the cache offloads from the DB."},
        {"label": "Target hit rate", "value": "95%+", "note": "Misses fall through to the DB; the residual load must be survivable."},
        {"label": "Cached data", "value": "TBs", "note": "Spread across many nodes' RAM."},
        {"label": "Value size", "value": "~KBs", "note": "Larger values reduce entries per node."},
        {"label": "Hit latency", "value": "sub-ms", "note": "In-memory + network round trip."},
    ],

    "api": [
        {"method": "GET", "path": "cache.get(key)",
         "description": "Read a key; returns the cached value or a miss.",
         "request": "get(\"user:42\")",
         "response": "value | MISS",
         **seq(
             [{"id": "App"}, {"id": "ClientLib", "label": "Cache Client"}, {"id": "CacheA", "label": "Cache Node"}, {"id": "DB", "label": "Database"}],
             [
                 {"from": "App", "to": "ClientLib", "arrow": "->>", "label": "get(user:42)"},
                 {"from": "ClientLib", "to": "CacheA", "arrow": "->>", "label": "hash -> node A"},
                 {"type": "alt", "label": "hit",
                  "messages": [{"from": "CacheA", "to": "App", "arrow": "-->>", "label": "value"}],
                  "else": {"label": "miss",
                           "messages": [
                               {"from": "App", "to": "DB", "arrow": "->>", "label": "load"},
                               {"from": "App", "to": "CacheA", "arrow": "->>", "label": "set (backfill)"},
                           ]}},
             ])},
        {"method": "SET", "path": "cache.set(key, value, ttl)",
         "description": "Write a value with an optional TTL.",
         "request": "set(\"user:42\", {...}, ttl=300)",
         "response": "OK"},
        {"method": "DEL", "path": "cache.delete(key)",
         "description": "Invalidate a key (e.g. after a DB write).",
         "request": "delete(\"user:42\")",
         "response": "OK"},
    ],

    "dataModel": [
        {"name": "cache entry (per node, in memory)", "note": "What a cache node holds.",
         "fields": [
             {"name": "key", "type": "string"},
             {"name": "value", "type": "bytes (serialized)"},
             {"name": "expires_at", "type": "timestamp (TTL)"},
             {"name": "lru_meta", "type": "recency/frequency bookkeeping for eviction"},
         ]},
        {"name": "ring / topology", "note": "Control-plane mapping of key ranges to nodes.",
         "fields": [
             {"name": "token", "type": "ring position"},
             {"name": "node_id", "type": "owner"},
             {"name": "vnodes", "type": "list<token>"},
             {"name": "health", "type": "up | down"},
         ]},
    ],

    "patterns": [
        {"name": "Cache-aside (lazy loading)", "what": "App checks cache, loads from DB on miss, and backfills the cache.",
         "whenToUse": "Read-heavy data tolerant of brief staleness; the default caching pattern.", "steps": ["cache-aside"]},
        {"name": "Consistent hashing", "what": "Map keys to cache nodes on a ring so adding/removing a node moves few keys.",
         "whenToUse": "Sharding a cache where node count changes and you want minimal cache churn.", "steps": ["sharding"]},
        {"name": "Eviction policy (LRU/LFU/TTL)", "what": "Reclaim memory by dropping least-useful entries when full.",
         "whenToUse": "Any bounded-memory cache; the policy shapes the hit rate.", "steps": ["eviction"]},
        {"name": "Write-through / write-back", "what": "Update the cache on writes (synchronously or asynchronously) to control consistency.",
         "whenToUse": "When stale reads after a write are unacceptable, or to absorb write bursts.", "steps": ["consistency"]},
        {"name": "Replication + failover", "what": "Keep a replica of each node so a failure doesn't drop a whole shard.",
         "whenToUse": "When a cold shard would overload the DB on failover.", "steps": ["failover"]},
        {"name": "Request coalescing (anti-stampede)", "what": "Collapse concurrent misses for the same key into one DB load.",
         "whenToUse": "Hot keys where a miss could trigger a thundering herd.", "steps": ["hotkeys"]},
    ],

    "steps": [
        {
            "id": "cache-aside",
            "title": "1. Cache-Aside in Front of the Database",
            "description": [
                "The application reads through the cache: on a hit it returns the value; on a miss it loads from the database and backfills the cache with a TTL.",
                "This is the cache-aside (lazy-loading) pattern. The cache holds only what's actually been requested, and the DB stays the source of truth.",
                "Even a single cache node here dramatically cuts DB read load — but one node caps memory and throughput and is a single point of failure.",
            ],
            "view": view(["App", "ClientLib", "CacheA", "DB"],
                         ["app-clientlib", "clientlib-a", "a-db", "app-db"],
                         highlight=["CacheA"], groups=["cache-tier"]),
            "decisionPrompt": "On a miss, who loads from the DB and backfills — the app or the cache node?",
            "concepts": [
                {"term": "Cache-aside", "definition": "App checks cache, reads DB on miss, then writes the value back into the cache.",
                 "whyItMatters": "Simple, resilient (a cache outage just means more DB load), and caches only hot data.",
                 "example": "GET user:42 -> miss -> SELECT from DB -> SET user:42 with TTL."},
            ],
            "patterns": ["Cache-aside (lazy loading)"],
            "whyNow": ["Cache-aside is the baseline contract; every later concern (sharding, eviction, consistency) is layered on this read path."],
            "recap": {"before": "All reads hit the DB.", "after": "Hot reads served from memory; DB load drops sharply.",
                      "newRisk": "One node limits memory/throughput and is a SPOF; need to shard."},
            "traps": [
                {"trap": "Caching on write only (never on read).", "why": "Cold or evicted keys never repopulate, so hit rate collapses for read-heavy data.",
                 "instead": "Lazy-load on miss so the working set self-populates."},
            ],
        },
        {
            "id": "sharding",
            "title": "2. Shard the Keyspace with Consistent Hashing",
            "description": [
                "To exceed one node's memory and throughput, partition keys across many cache nodes. Hash each key to a node on a consistent-hashing ring (with virtual nodes for even load).",
                "Consistent hashing means adding or removing a node only remaps that node's share of keys — not the whole keyspace — so a scaling event doesn't blow away the entire cache and stampede the DB.",
                "Routing can live in a client library (client hashes and talks to nodes directly) or a proxy/router tier; both read the ring topology from a config/membership service.",
            ],
            "view": view(["ClientLib", "Router", "CacheA", "CacheB", "CacheC", "Config"],
                         ["clientlib-router", "router-a", "router-b", "router-c", "config-router", "config-clientlib"],
                         highlight=["CacheA", "CacheB", "CacheC", "Router"], groups=["cache-tier", "control"]),
            "decisionPrompt": "With plain key % N hashing, what happens to the hit rate when one node dies?",
            "concepts": [
                {"term": "Consistent hashing", "definition": "Hash keys and nodes onto a ring; a key belongs to the next node clockwise.",
                 "whyItMatters": "A node change remaps ~1/N of keys instead of nearly all — avoids a cache-wide miss storm.",
                 "example": "Drop one of 10 nodes -> only ~10% of keys remap, not 100%."},
            ],
            "patterns": ["Consistent hashing"],
            "whyNow": ["Sharding is how the cache scales; consistent hashing is specifically what protects the DB during topology changes."],
            "recap": {"before": "Single node.", "after": "Keyspace spread across nodes; scaling moves minimal keys.",
                      "newRisk": "Each node has bounded RAM — it must decide what to drop when full."},
            "traps": [
                {"trap": "Sharding with key modulo node-count.", "why": "Changing node count remaps almost every key, causing a near-total cache miss and a DB stampede.",
                 "instead": "Consistent hashing with virtual nodes."},
            ],
        },
        {
            "id": "eviction",
            "title": "3. Eviction: Make Room When Memory Is Full",
            "description": [
                "Cache memory is bounded, so when a node fills up it must evict entries. The policy determines which entries survive and therefore the hit rate.",
                "LRU (least-recently-used) is the common default; LFU (least-frequently-used) better protects truly hot keys from a burst of one-offs; TTL expiry bounds staleness regardless.",
                "Eviction is per-node and continuous. Size values and TTLs so the working set fits; monitor evictions/sec as an early warning that the tier is undersized.",
            ],
            "view": view(["App", "CacheA", "Eviction", "DB"],
                         ["clientlib-a", "eviction-a", "a-db"],
                         highlight=["Eviction"], groups=["cache-tier", "control"]),
            "decisionPrompt": "A scan reads a million cold keys once. Why might that hurt your hit rate under LRU, and what helps?",
            "concepts": [
                {"term": "LRU vs LFU", "definition": "Evict the least-recently-used vs least-frequently-used entry.",
                 "whyItMatters": "LRU is cheap but vulnerable to scans; LFU protects hot keys but needs frequency tracking.",
                 "example": "A one-time scan evicts hot keys under pure LRU; LFU (or scan-resistant LRU) keeps them."},
            ],
            "patterns": ["Eviction policy (LRU/LFU/TTL)"],
            "whyNow": ["Eviction is what turns 'infinite cache' fantasy into a real bounded-memory tier; the policy choice directly drives the hit-rate requirement."],
            "recap": {"before": "Assumed unlimited memory.", "after": "Bounded memory with a policy that protects hot data.",
                      "newRisk": "After a write to the DB, cached copies are stale — need a consistency strategy."},
        },
        {
            "id": "consistency",
            "title": "4. Cache/DB Consistency on Writes",
            "description": [
                "The cache and DB can disagree after a write. Pick a strategy: cache-aside with invalidation (delete the key on DB write, repopulate lazily), write-through (write cache + DB synchronously), or write-back (write cache now, flush to DB async).",
                "Invalidate-on-write is the common, robust choice: it avoids serving the old value and lets the next read repopulate. Write-through keeps the cache warm but adds write latency; write-back is fast but risks loss on node failure.",
                "Name the race: a read-miss can backfill a stale value if it interleaves with a write. Mitigate with delete (not update) on write, short TTLs, or versioned keys.",
            ],
            "view": view(["App", "CacheA", "DB"],
                         ["app-cachea", "app-db", "a-db"],
                         highlight=["CacheA", "DB"], groups=["cache-tier"]),
            "decisionPrompt": "Update the DB then the cache, or delete the cache then update the DB? What can go wrong in each order?",
            "concepts": [
                {"term": "Invalidate-on-write", "definition": "Delete the cached key when the DB changes, letting the next read repopulate.",
                 "whyItMatters": "Avoids the hard problem of keeping two copies perfectly in sync.",
                 "example": "UPDATE users SET ... -> DELETE cache user:42 -> next GET reloads fresh."},
                {"term": "Write-through vs write-back", "definition": "Write cache+DB together vs write cache now and flush DB later.",
                 "whyItMatters": "Trades write latency and durability against freshness.",
                 "example": "Write-back absorbs bursts but can lose unflushed writes if the node dies."},
            ],
            "patterns": ["Write-through / write-back"],
            "whyNow": ["Consistency is the subtle part interviewers push on; articulating invalidate-on-write and the read-miss race is the senior differentiator."],
            "flows": [
                seq(
                    [{"id": "App"}, {"id": "DB", "label": "Database"}, {"id": "CacheA", "label": "Cache Node"}],
                    [
                        {"from": "App", "to": "DB", "arrow": "->>", "label": "UPDATE row"},
                        {"from": "App", "to": "CacheA", "arrow": "->>", "label": "DELETE key (invalidate)"},
                        {"from": "App", "to": "App", "arrow": "->>", "label": "next read -> miss -> reload fresh"},
                    ],
                    highlight=["CacheA"]),
            ],
            "recap": {"before": "Reads could serve stale data indefinitely.", "after": "Writes invalidate; staleness is bounded and reasoned about.",
                      "newRisk": "A single hot key can still overwhelm one node, and node failure drops a shard cold."},
            "traps": [
                {"trap": "Updating the cache value on write instead of deleting it.", "why": "Concurrent writes can interleave and leave the wrong value cached.",
                 "instead": "Delete (invalidate) and let the next read repopulate the authoritative value."},
            ],
        },
        {
            "id": "hotkeys",
            "title": "5. Hot Keys and Thundering Herds",
            "description": [
                "A single very popular key (a celebrity profile, a flash-sale item) concentrates traffic on one node — a hot shard the ring can't spread.",
                "When that key expires or is evicted, all concurrent readers miss at once and hammer the DB: a cache stampede / thundering herd. Coalesce concurrent misses so only one request loads from the DB and the rest wait for it.",
                "For extreme hot keys, replicate the key across multiple nodes (or add a tiny local in-process cache) so reads spread; refresh popular keys slightly before expiry to avoid synchronized misses.",
            ],
            "view": view(["App", "ClientLib", "CacheA", "Replica", "DB"],
                         ["app-clientlib", "clientlib-a", "a-replica", "a-db"],
                         highlight=["Replica"], groups=["cache-tier"]),
            "decisionPrompt": "10,000 requests/sec read one key. It expires. What happens to the DB, and how do you prevent it?",
            "concepts": [
                {"term": "Cache stampede", "definition": "Many concurrent misses for the same key flooding the backing store at once.",
                 "whyItMatters": "A single expiry can spike DB load enough to cause an outage.",
                 "example": "Hot key TTL fires -> 10K simultaneous misses -> DB overload."},
                {"term": "Request coalescing", "definition": "Letting one request fill the cache while concurrent misses wait for its result.",
                 "whyItMatters": "Turns a herd into a single DB load.",
                 "example": "First miss takes a per-key lock and loads; others block briefly, then read the backfilled value."},
            ],
            "patterns": ["Request coalescing (anti-stampede)"],
            "whyNow": ["Hot keys are the failure mode sharding alone can't fix; coalescing + key replication is the expected mitigation."],
            "recap": {"before": "Uniform-load assumption.", "after": "Hot keys spread/replicated; stampedes coalesced.",
                      "newRisk": "A node failure still drops its whole shard cold — need replication/failover."},
            "traps": [
                {"trap": "Relying on consistent hashing to spread a single hot key.", "why": "One key hashes to exactly one node; the ring can't split it.",
                 "instead": "Replicate the hot key across nodes / add a local cache, and coalesce misses."},
            ],
        },
        {
            "id": "failover",
            "title": "6. Replication, Failover, and Failure Modes",
            "description": [
                "If a cache node dies, its entire shard is suddenly cold and every key on it misses to the DB — potentially a load spike that takes the DB down. Mitigate by keeping a replica per primary that can take over warm.",
                "A membership/config service tracks node health; clients/routers refresh the ring and route around a dead node. With virtual nodes, a failed node's keys spread across many peers rather than dogpiling one.",
                "Treat the cache as best-effort: the app must remain correct (if slower) with the cache empty. Add jittered TTLs and rate-limited backfill so a cold start doesn't stampede the DB.",
            ],
            "view": view(["App", "ClientLib", "CacheA", "Replica", "Config", "DB"],
                         ["clientlib-a", "a-replica", "replica-app", "config-clientlib", "a-db"],
                         highlight=["Replica", "Config"], groups=["cache-tier", "control"]),
            "decisionPrompt": "A cache node holding 10% of keys dies. What does the DB suddenly experience, and how do you cushion it?",
            "patterns": ["Replication + failover"],
            "whyNow": ["Closing on failure modes shows the cache improves performance without becoming a new SPOF — the reliability requirement."],
            "recap": {"before": "Node loss = cold shard + DB spike.", "after": "Replicas warm-failover; ring routes around failures; cold starts are cushioned.",
                      "newRisk": "Replication doubles memory cost; stale replicas — bounded by acceptable cache staleness."},
            "failureDrills": [
                {"scenario": "A primary cache node fails.",
                 "expectedBehavior": "Its replica serves the shard warm; the ring updates so clients route to it; the DB sees little extra load.",
                 "mitigation": "Per-primary replica + health-driven routing + virtual nodes."},
                {"scenario": "The entire cache tier is unavailable.",
                 "expectedBehavior": "The app still works (correctly) by reading the DB directly, just slower.",
                 "mitigation": "Cache-aside keeps the DB authoritative; rate-limit/jitter backfill to avoid stampede on recovery."},
            ],
        },
    ],

    "finalDesign": {
        "title": "Final Design — Sharded, Replicated Cache Tier",
        "description": "Applications read cache-aside through a client library (or proxy) that consistent-hashes keys across many in-memory cache nodes, with virtual nodes for even load and a config service tracking topology/health. Each node evicts under memory pressure (LRU/LFU + TTL). Writes invalidate cached keys to bound staleness. Hot keys are replicated and concurrent misses coalesced to prevent stampedes; per-primary replicas provide warm failover so a node loss doesn't cold-spike the database, which always remains the source of truth.",
        "view": view(
            ["App", "ClientLib", "Router", "CacheA", "CacheB", "CacheC", "Replica", "Config", "Eviction", "DB"],
            ["app-clientlib", "clientlib-router", "router-a", "router-b", "router-c", "clientlib-a",
             "a-db", "app-db", "a-replica", "replica-app", "config-clientlib", "config-router",
             "eviction-a", "app-cachea"],
            groups=["cache-tier", "control"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "get/set/delete with TTL", "how": "Cache-aside read path; per-entry TTL; invalidate on write.", "steps": ["cache-aside", "consistency"]},
            {"requirement": "Scale capacity by adding nodes", "how": "Consistent-hashing sharding with virtual nodes.", "steps": ["sharding"]},
        ],
        "nonFunctional": [
            {"requirement": "Sub-ms hit latency", "how": "In-memory nodes reached directly via client hashing.", "steps": ["cache-aside", "sharding"]},
            {"requirement": "High hit rate", "how": "Lazy load + eviction policy that protects hot keys.", "steps": ["cache-aside", "eviction"]},
            {"requirement": "~1M+ ops/sec, TBs", "how": "Horizontal sharding across many nodes' RAM.", "steps": ["sharding"]},
            {"requirement": "Tolerate node failure", "how": "Replica failover + ring routing; DB stays authoritative.", "steps": ["failover"]},
            {"requirement": "Bounded staleness", "how": "Invalidate-on-write + TTLs.", "steps": ["consistency"]},
            {"requirement": "Survive hot keys", "how": "Key replication + request coalescing.", "steps": ["hotkeys"]},
        ],
    },

    "interviewScript": [
        {"phase": "Scope & requirements", "time": "first 5 min",
         "say": ["Confirm it's a look-aside cache in front of a DB, read-heavy.",
                 "Pin sub-ms hits and a high hit rate as the goals.",
                 "Agree staleness is acceptable but must be bounded and reasoned about."]},
        {"phase": "High-level design", "time": "next 10 min",
         "say": ["Cache-aside read path with backfill.",
                 "Shard with consistent hashing + virtual nodes.",
                 "Per-node eviction (LRU/LFU + TTL)."]},
        {"phase": "Deep dive", "time": "next 15 min",
         "say": ["Cache/DB consistency: invalidate-on-write and the read-miss race.",
                 "Hot keys and thundering herds: coalescing + key replication.",
                 "Replication/failover so node loss doesn't cold-spike the DB."]},
        {"phase": "Wrap-up", "time": "final 5 min",
         "say": ["Map requirements to mechanisms.",
                 "Tradeoffs: eviction policy, write-through vs invalidate, replication cost.",
                 "Extensions: multi-tier (local + remote) caching, near-cache, persistence."]},
    ],

    "levelVariants": [
        {"level": "Junior", "expectations": ["Uses cache-aside with TTLs.", "Shards across nodes.", "May miss stampedes and consistency races."]},
        {"level": "Senior", "expectations": ["Uses consistent hashing and reasons about eviction policy.", "Handles invalidate-on-write.", "Mitigates hot keys and stampedes."]},
        {"level": "Staff", "expectations": ["Reasons about cold-shard DB spikes on failover and cushions them.", "Discusses write-through vs write-back tradeoffs, multi-tier caching, and consistency races precisely."]},
    ],

    "followUps": [
        "When would you use write-through or write-back instead of invalidate-on-write?",
        "How do you prevent a synchronized mass-expiry from stampeding the DB?",
        "How would a local in-process cache layer interact with the distributed cache?",
        "How do you keep replicas consistent enough for warm failover?",
        "How would you add persistence so a restart doesn't start fully cold?",
    ],
}

if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
