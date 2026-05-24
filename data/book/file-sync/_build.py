#!/usr/bin/env python3
"""Builder for the Dropbox / File Sync book case."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

NODES = {
    "Client":    ("Sync Client (Device)", "client", "boundary", [], "Watches local folders, chunks files, and syncs changes both ways."),
    "LB":        ("API Gateway / LB", "edge", "traffic", ["stateless"], "Routes and authenticates sync and metadata requests."),
    "MetaSvc":   ("Metadata Service", "service", "compute", ["stateless"], "Owns the file/namespace tree, versions, and chunk lists."),
    "MetaDB":    ("Metadata Store", "database", "state", ["stateful"], "Authoritative file metadata, versions, and chunk manifests, sharded by user/namespace."),
    "BlockSvc":  ("Block Service", "service", "compute", ["stateless"], "Stores and retrieves content-addressed chunks; enforces dedup."),
    "BlockStore": ("Block / Object Store", "object-storage", "state", ["stateful"], "Durable storage for unique chunks, keyed by content hash."),
    "ChunkIdx":  ("Chunk Index", "index", "state", ["stateful", "derived"], "hash -> exists? + refcount; powers dedup and garbage collection."),
    "NotifySvc": ("Notification Service", "service", "async", ["stateful"], "Long-poll/push channel telling other devices a namespace changed."),
    "NotifyQ":   ("Change Notification Queue", "queue", "async", [], "Buffers change events fanned out to a user's other devices."),
    "CDN":       ("Download CDN", "edge", "traffic", ["stateful", "derived"], "Caches popular/public chunks near users for fast download."),
    "GC":        ("Garbage Collector", "worker", "async", ["stateless"], "Reclaims chunks whose refcount drops to zero."),
}

LINKS = {
    "client-lb":        ("Client", "LB", "HTTPS"),
    "lb-meta":          ("LB", "MetaSvc", "metadata ops"),
    "lb-block":         ("LB", "BlockSvc", "chunk up/download"),
    "meta-metadb":      ("MetaSvc", "MetaDB", "read/write tree + versions"),
    "block-chunkidx":   ("BlockSvc", "ChunkIdx", "hash exists?"),
    "block-store":      ("BlockSvc", "BlockStore", "put/get chunk"),
    "client-block":     ("Client", "BlockSvc", "upload missing chunks"),
    "client-meta":      ("Client", "MetaSvc", "commit file version"),
    "meta-notify":      ("MetaSvc", "NotifySvc", "namespace changed"),
    "notify-q":         ("NotifySvc", "NotifyQ", "enqueue change"),
    "q-client":         ("NotifyQ", "Client", "notify other devices"),
    "client-cdn":       ("Client", "CDN", "download chunk"),
    "cdn-store":        ("CDN", "BlockStore", "origin fetch"),
    "gc-chunkidx":      ("GC", "ChunkIdx", "find refcount=0"),
    "gc-store":         ("GC", "BlockStore", "delete chunk"),
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
        {"id": "metadata-plane", "label": "Metadata Plane", "nodes": ["MetaSvc", "MetaDB", "NotifySvc"]},
        {"id": "block-plane", "label": "Block / Storage Plane", "nodes": ["BlockSvc", "BlockStore", "ChunkIdx", "CDN"]},
    ]
    return {"nodes": nodes, "links": links, "types": types}


def seq(parts, msgs, highlight=None):
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight: out["highlight"] = highlight
    return out


data = {
    "title": "Dropbox / File Sync — System Design",
    "description": "Design a file storage and sync service: upload files, store them durably and cheaply, and keep the same folder consistent across a user's devices. The themes are splitting files into content-addressed chunks, deduplication, the metadata/block split, and change notification.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  User[User]",
        "  Upload[Upload / edit file]",
        "  Store[Store durably]",
        "  Sync[Sync to other devices]",
        "  Share[Share with others]",
        "  User --> Upload",
        "  Upload --> Store",
        "  Store --> Sync",
        "  Sync --> Share",
    ],
    "capacityDiagram": [
        "graph LR",
        "  Files[Billions of files]",
        "  Bytes[Exabytes of data]",
        "  Dedup[High dedup ratio]",
        "  Files --> Bytes",
        "  Bytes --> Dedup",
    ],

    "requirements": {
        "functional": [
            "Upload, download, and delete files of arbitrary size.",
            "Sync a folder so the same files appear on all of a user's devices.",
            "Versioning: keep history; restore a previous version.",
            "Share files/folders with other users (read or write).",
            "Resumable uploads that survive flaky connections.",
        ],
        "nonFunctional": [
            "Durable: never lose a stored file (11 nines style durability).",
            "Storage-efficient: deduplicate identical content to control cost.",
            "Bandwidth-efficient sync: transfer only what changed, not whole files.",
            "Sync latency: a change appears on other devices within seconds.",
            "Scale to billions of files / exabytes; read-heavy on downloads.",
        ],
    },

    "capacity": [
        {"label": "Files", "value": "billions", "note": "Across hundreds of millions of users."},
        {"label": "Total bytes", "value": "exabytes", "note": "Dominated by media and backups."},
        {"label": "Chunk size", "value": "~4 MB", "note": "Unit of dedup, transfer, and resumability."},
        {"label": "Dedup ratio", "value": "high", "note": "Shared files, re-uploads, and unchanged chunks dedup heavily."},
        {"label": "Read:write", "value": "downloads >> uploads", "note": "Justifies a download CDN."},
    ],

    "api": [
        {"method": "POST", "path": "/v1/chunks/check",
         "description": "Given chunk hashes, return which are missing so the client only uploads those.",
         "request": "{ \"hashes\": [\"h1\", \"h2\", \"h3\"] }",
         "response": "{ \"missing\": [\"h2\"] }",
         **seq(
             [{"id": "Client"}, {"id": "BlockSvc", "label": "Block Service"}, {"id": "ChunkIdx", "label": "Chunk Index"}],
             [
                 {"from": "Client", "to": "BlockSvc", "arrow": "->>", "label": "check hashes"},
                 {"from": "BlockSvc", "to": "ChunkIdx", "arrow": "->>", "label": "which exist?"},
                 {"from": "BlockSvc", "to": "Client", "arrow": "-->>", "label": "missing: [h2]"},
             ])},
        {"method": "PUT", "path": "/v1/chunks/{hash}",
         "description": "Upload one content-addressed chunk. Idempotent: same hash, same content.",
         "request": "(raw chunk bytes, ~4MB)",
         "response": "{ \"stored\": true }"},
        {"method": "POST", "path": "/v1/files/commit",
         "description": "Commit a new file version referencing its ordered chunk hashes. Triggers sync notifications.",
         "request": "{ \"path\": \"/docs/a.pdf\", \"chunks\": [\"h1\",\"h2\",\"h3\"], \"baseVersion\": 7 }",
         "response": "{ \"version\": 8 }",
         **seq(
             [{"id": "Client"}, {"id": "MetaSvc", "label": "Metadata Service"}, {"id": "MetaDB", "label": "Metadata Store"},
              {"id": "NotifySvc", "label": "Notify Service"}],
             [
                 {"from": "Client", "to": "MetaSvc", "arrow": "->>", "label": "commit version (chunk list)"},
                 {"from": "MetaSvc", "to": "MetaDB", "arrow": "->>", "label": "write version 8"},
                 {"from": "MetaSvc", "to": "NotifySvc", "arrow": "->>", "label": "namespace changed"},
                 {"from": "MetaSvc", "to": "Client", "arrow": "-->>", "label": "200 version=8"},
             ])},
        {"method": "GET", "path": "/v1/files/changes",
         "description": "Long-poll for changes to the user's namespace since a cursor (the sync delta).",
         "request": "?cursor=<opaque>",
         "response": "{ \"changes\": [ ... ], \"cursor\": \"...\" }"},
    ],

    "dataModel": [
        {"name": "files (metadata)", "note": "Current state of a path in a namespace.",
         "fields": [
             {"name": "namespace_id", "type": "bigint (shard key)"},
             {"name": "path", "type": "varchar"},
             {"name": "version", "type": "bigint"},
             {"name": "chunk_hashes", "type": "list<varchar> (ordered)"},
             {"name": "size", "type": "bigint"},
             {"name": "deleted", "type": "bool"},
         ]},
        {"name": "versions", "note": "Immutable version history per file for restore.",
         "fields": [
             {"name": "file_id", "type": "bigint"},
             {"name": "version", "type": "bigint"},
             {"name": "chunk_hashes", "type": "list<varchar>"},
             {"name": "created_at", "type": "timestamp"},
         ]},
        {"name": "chunks", "note": "Content-addressed dedup index (one row per unique chunk).",
         "fields": [
             {"name": "hash", "type": "varchar PK (e.g. SHA-256 of content)"},
             {"name": "size", "type": "int"},
             {"name": "refcount", "type": "bigint (for GC)"},
             {"name": "location", "type": "object-store key"},
         ]},
    ],

    "patterns": [
        {"name": "Content-addressed chunking", "what": "Split files into fixed/variable chunks and key each by the hash of its content.",
         "whenToUse": "Storage where identical content recurs and partial transfer matters.", "steps": ["chunking"]},
        {"name": "Deduplication", "what": "Store each unique chunk once; reference it by hash from many files.",
         "whenToUse": "When the same bytes appear across files, versions, and users.", "steps": ["dedup"]},
        {"name": "Metadata/data split", "what": "Keep the file tree and chunk manifests in a transactional store; keep bytes in cheap object storage.",
         "whenToUse": "Large-blob systems needing both rich metadata and cheap durable bytes.", "steps": ["meta-split"]},
        {"name": "Delta sync", "what": "Transfer only changed chunks by comparing hashes before upload/download.",
         "whenToUse": "Bandwidth-constrained sync of large files with small edits.", "steps": ["sync"]},
        {"name": "Change notification (long-poll/push)", "what": "Tell other devices a namespace changed so they pull the delta.",
         "whenToUse": "Near-real-time multi-device sync without constant polling.", "steps": ["notify"]},
        {"name": "Reference-counted GC", "what": "Track chunk refcounts and reclaim chunks no version references.",
         "whenToUse": "Dedup stores where deletes must eventually free space safely.", "steps": ["gc"]},
    ],

    "steps": [
        {
            "id": "chunking",
            "title": "1. Split Files into Content-Addressed Chunks",
            "description": [
                "The client splits each file into chunks (~4 MB) and hashes each chunk's content. The hash is the chunk's identity (content-addressed storage).",
                "Chunking is the unit of everything: transfer, dedup, resumability, and versioning. A small edit re-chunks only the affected region, not the whole file.",
                "The client uploads chunks to the block service and records the ordered list of chunk hashes that reconstructs the file.",
            ],
            "view": view(["Client", "LB", "BlockSvc", "BlockStore"],
                         ["client-lb", "lb-block", "block-store"],
                         highlight=["BlockSvc", "BlockStore"], groups=["block-plane"]),
            "decisionPrompt": "Fixed-size vs content-defined (variable) chunking — what does each cost when you insert a byte at the start of a file?",
            "concepts": [
                {"term": "Content-addressed chunk", "definition": "A block of bytes identified by the hash of its own content.",
                 "whyItMatters": "Identical content has the same id everywhere, which is what makes dedup and delta sync possible.",
                 "example": "chunk hash = SHA-256(bytes); same bytes -> same hash -> stored once."},
            ],
            "patterns": ["Content-addressed chunking"],
            "whyNow": ["Chunking is the foundational decision; dedup, delta sync, and resumability all derive from it."],
            "recap": {"before": "Nothing.", "after": "Files are ordered lists of content-addressed chunks.",
                      "newRisk": "Many chunks will be identical across files/users — storing them all is wasteful; need dedup."},
            "traps": [
                {"trap": "Fixed-size chunking with no rolling hash.", "why": "Inserting one byte at the front shifts all boundaries, so every chunk hash changes and dedup collapses.",
                 "instead": "Use content-defined chunking (rolling hash) so boundaries are stable under edits."},
            ],
        },
        {
            "id": "dedup",
            "title": "2. Deduplicate: Store Each Chunk Once",
            "description": [
                "Before uploading, the client asks the block service which chunk hashes already exist (the chunk index). It uploads only the missing ones.",
                "This dedups across versions (an edit re-sends only changed chunks), across files, and across users (the same shared PDF is stored once).",
                "The chunk index maps hash -> exists + refcount; the actual bytes live once in the object store keyed by hash.",
            ],
            "view": view(["Client", "BlockSvc", "ChunkIdx", "BlockStore"],
                         ["client-block", "block-chunkidx", "block-store"],
                         highlight=["ChunkIdx"], groups=["block-plane"]),
            "decisionPrompt": "How much bandwidth does saving a 1 GB video with a 1-second trim re-cost?",
            "patterns": ["Deduplication"],
            "whyNow": ["Dedup is the cost story for a storage system; the 'check-then-upload-missing' handshake is the concrete mechanism interviewers want."],
            "flows": [
                seq(
                    [{"id": "Client"}, {"id": "BlockSvc", "label": "Block Service"},
                     {"id": "ChunkIdx", "label": "Chunk Index"}, {"id": "BlockStore", "label": "Block Store"}],
                    [
                        {"from": "Client", "to": "BlockSvc", "arrow": "->>", "label": "check [h1,h2,h3]"},
                        {"from": "BlockSvc", "to": "ChunkIdx", "arrow": "->>", "label": "which exist?"},
                        {"from": "BlockSvc", "to": "Client", "arrow": "-->>", "label": "missing: [h2]"},
                        {"from": "Client", "to": "BlockSvc", "arrow": "->>", "label": "PUT h2 only"},
                        {"from": "BlockSvc", "to": "BlockStore", "arrow": "->>", "label": "store h2"},
                    ],
                    highlight=["ChunkIdx"]),
            ],
            "recap": {"before": "Every chunk uploaded and stored.", "after": "Only novel chunks transfer and store.",
                      "newRisk": "Need a place for the file tree, versions, and chunk manifests — separate from the bytes."},
        },
        {
            "id": "meta-split",
            "title": "3. Split Metadata from Block Storage",
            "description": [
                "Keep two planes. The metadata service owns the namespace tree, file versions, and each file's ordered chunk-hash manifest in a transactional database. The block plane stores opaque bytes cheaply and durably in object storage.",
                "A 'file' is just metadata: a path + version + list of chunk hashes. Reconstructing it means fetching those chunks. This keeps the rich, queryable, transactional part small and the huge part cheap.",
                "Commit metadata last: upload chunks first, then atomically commit the new version referencing them. A crash mid-upload leaves orphan chunks (GC handles them), never a dangling metadata pointer.",
            ],
            "view": view(["Client", "LB", "MetaSvc", "MetaDB", "BlockSvc", "BlockStore"],
                         ["lb-meta", "meta-metadb", "client-meta", "lb-block", "block-store"],
                         highlight=["MetaSvc", "MetaDB"], groups=["metadata-plane", "block-plane"]),
            "decisionPrompt": "Why not store file bytes directly in the metadata database?",
            "concepts": [
                {"term": "Metadata/data split", "definition": "Separate the transactional file tree/manifest from the bulk byte storage.",
                 "whyItMatters": "Lets metadata be consistent and queryable while bytes stay cheap and massively scalable.",
                 "example": "Postgres-style metadata DB + S3-style block store."},
            ],
            "patterns": ["Metadata/data split"],
            "whyNow": ["The metadata/data split is the architectural backbone; ordering chunk-upload before metadata-commit is the correctness nuance."],
            "recap": {"before": "Bytes and structure intermingled.", "after": "Transactional metadata + cheap durable blocks; commit ordering is safe.",
                      "newRisk": "Multiple devices editing the same namespace need to converge — sync + conflicts."},
            "traps": [
                {"trap": "Committing metadata before chunks are durably stored.", "why": "A reader could resolve a version whose chunks don't exist yet.",
                 "instead": "Upload chunks first; commit the version referencing them last."},
            ],
        },
        {
            "id": "sync",
            "title": "4. Delta Sync Across Devices",
            "description": [
                "Each device tracks a cursor of the last namespace version it has seen. To sync, it asks for the changes since its cursor and gets a delta of changed file metadata.",
                "For each changed file, the device compares the new chunk-hash list against what it already has locally and downloads only the missing chunks — delta sync in both directions.",
                "Downloads come from the block service or a CDN; reconstruct the file from its ordered chunks. Resumable because chunks are independent units.",
            ],
            "view": view(["Client", "MetaSvc", "MetaDB", "BlockSvc", "CDN", "BlockStore"],
                         ["client-meta", "meta-metadb", "client-block", "client-cdn", "cdn-store"],
                         highlight=["CDN"], groups=["metadata-plane", "block-plane"]),
            "decisionPrompt": "A 500 MB file changed by 4 MB. How much does each other device download?",
            "patterns": ["Delta sync"],
            "whyNow": ["Bandwidth-efficient sync is a headline requirement; reusing the hash-compare from dedup on the download side is the elegant part."],
            "recap": {"before": "Whole-file transfer.", "after": "Devices transfer only changed chunks, resumably, via CDN.",
                      "newRisk": "How do devices learn there's a change without constant polling? And what if two devices edit at once?"},
        },
        {
            "id": "notify",
            "title": "5. Change Notification and Conflict Handling",
            "description": [
                "On commit, the metadata service publishes a 'namespace changed' event; a notification service (long-poll or push) tells the user's other devices to pull the delta — near-real-time without polling.",
                "Concurrent edits are detected with optimistic versioning: a commit carries the baseVersion it edited; if the server has advanced past it, the commit conflicts.",
                "Resolve conflicts safely by keeping both: create a 'conflicted copy' rather than silently overwriting, and let the user reconcile. Never lose a write.",
            ],
            "view": view(["MetaSvc", "NotifySvc", "NotifyQ", "Client"],
                         ["meta-notify", "notify-q", "q-client"],
                         highlight=["NotifySvc", "NotifyQ"], groups=["metadata-plane"]),
            "decisionPrompt": "Two devices edit the same file offline, then both reconnect. What should happen?",
            "concepts": [
                {"term": "Optimistic version check", "definition": "A commit names the version it was based on; the server rejects it if state moved on.",
                 "whyItMatters": "Detects concurrent edits without locking the file.",
                 "example": "Commit baseVersion=7 fails if the file is now at version 8 -> conflict."},
            ],
            "patterns": ["Change notification (long-poll/push)"],
            "whyNow": ["Notification turns 'eventually correct' into 'syncs in seconds'; the conflict policy is the data-safety nuance senior interviewers probe."],
            "flows": [
                seq(
                    [{"id": "Client"}, {"id": "MetaSvc", "label": "Metadata Service"}, {"id": "NotifySvc", "label": "Notify Service"}],
                    [
                        {"from": "Client", "to": "MetaSvc", "arrow": "->>", "label": "commit baseVersion=7"},
                        {"type": "alt", "label": "no conflict",
                         "messages": [
                             {"from": "MetaSvc", "to": "Client", "arrow": "-->>", "label": "200 version=8"},
                             {"from": "MetaSvc", "to": "NotifySvc", "arrow": "->>", "label": "notify other devices"},
                         ],
                         "else": {"label": "stale base (conflict)",
                                  "messages": [{"from": "MetaSvc", "to": "Client", "arrow": "-->>", "label": "409 -> create conflicted copy"}]}},
                    ],
                    highlight=["NotifySvc"]),
            ],
            "recap": {"before": "Devices polled and could clobber edits.", "after": "Push-driven sync; concurrent edits kept as conflicted copies.",
                      "newRisk": "Deletes and old versions accumulate dead chunks — need GC."},
            "traps": [
                {"trap": "Last-writer-wins overwrite on conflict.", "why": "Silently destroys one user's edits.",
                 "instead": "Keep both via a conflicted copy and let the user reconcile."},
            ],
        },
        {
            "id": "gc",
            "title": "6. Garbage Collection and Durability",
            "description": [
                "Dedup means a chunk may be referenced by many files/versions. Deleting a file or pruning old versions doesn't free a chunk until nothing references it — track a refcount per chunk.",
                "A background garbage collector finds chunks whose refcount hit zero and deletes them from the block store. Do this lazily and safely (grace period / mark-and-sweep) to avoid deleting a chunk a concurrent upload just referenced.",
                "Durability comes from the object store's replication/erasure coding across zones; metadata is replicated and backed up. Orphan chunks from interrupted uploads are reclaimed the same way.",
            ],
            "view": view(["GC", "ChunkIdx", "BlockStore", "MetaDB"],
                         ["gc-chunkidx", "gc-store", "meta-metadb"],
                         highlight=["GC"], groups=["block-plane", "metadata-plane"]),
            "decisionPrompt": "How do you avoid GC deleting a chunk that a just-started upload is about to reference?",
            "concepts": [
                {"term": "Reference-counted GC", "definition": "Reclaim a shared resource only when its reference count reaches zero.",
                 "whyItMatters": "Lets dedup and deletes coexist without freeing in-use data.",
                 "example": "Delete file -> decrement its chunks' refcounts -> GC removes any that hit 0."},
            ],
            "patterns": ["Reference-counted GC"],
            "whyNow": ["Closing on GC + durability shows the dedup design is complete: space is actually reclaimed, and data is safe."],
            "recap": {"before": "Deleted data lingered; durability implicit.", "after": "Refcounted GC reclaims unused chunks; bytes durably replicated.",
                      "newRisk": "GC races and zone failures — bounded by grace periods, mark-and-sweep, and cross-zone replication."},
            "failureDrills": [
                {"scenario": "An upload references a chunk just as GC is about to delete it.",
                 "expectedBehavior": "GC respects a grace period / re-checks refcount before delete, so the live chunk survives.",
                 "mitigation": "Mark-and-sweep with a delay; increment refcount before commit makes a chunk reachable."},
                {"scenario": "An availability zone holding chunks fails.",
                 "expectedBehavior": "Reads/writes continue from replicas in other zones.",
                 "mitigation": "Cross-zone replication / erasure coding in the object store."},
            ],
        },
    ],

    "finalDesign": {
        "title": "Final Design — Chunked, Deduplicated File Sync",
        "description": "Clients chunk files into content-addressed blocks, check the chunk index, and upload only missing chunks to the block store; then they commit a new file version (ordered chunk hashes) to the transactional metadata service. The metadata/block split keeps structure consistent and bytes cheap. The notification service pushes change events so other devices pull deltas and download only changed chunks (via CDN). Concurrent edits become conflicted copies; reference-counted GC reclaims unused chunks; the object store provides cross-zone durability.",
        "view": view(
            ["Client", "LB", "MetaSvc", "MetaDB", "BlockSvc", "BlockStore", "ChunkIdx",
             "NotifySvc", "NotifyQ", "CDN", "GC"],
            ["client-lb", "lb-meta", "lb-block", "meta-metadb", "block-chunkidx", "block-store",
             "client-block", "client-meta", "meta-notify", "notify-q", "q-client", "client-cdn",
             "cdn-store", "gc-chunkidx", "gc-store"],
            groups=["metadata-plane", "block-plane"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "Upload / download / delete", "how": "Chunked upload to block store; metadata commit; refcount on delete.", "steps": ["chunking", "meta-split", "gc"]},
            {"requirement": "Multi-device sync", "how": "Cursor-based delta + push notification; download only changed chunks.", "steps": ["sync", "notify"]},
            {"requirement": "Versioning + restore", "how": "Immutable version rows referencing chunk manifests.", "steps": ["meta-split"]},
            {"requirement": "Resumable uploads", "how": "Independent content-addressed chunks; re-check missing and resume.", "steps": ["chunking", "dedup"]},
        ],
        "nonFunctional": [
            {"requirement": "Durability", "how": "Cross-zone replication/erasure coding in the object store; replicated metadata.", "steps": ["gc"]},
            {"requirement": "Storage efficiency", "how": "Content-addressed dedup stores each chunk once.", "steps": ["dedup"]},
            {"requirement": "Bandwidth-efficient sync", "how": "Hash-compare transfers only changed chunks both ways.", "steps": ["dedup", "sync"]},
            {"requirement": "Seconds-level sync latency", "how": "Push notifications drive pulls instead of polling.", "steps": ["notify"]},
        ],
    },

    "interviewScript": [
        {"phase": "Scope & requirements", "time": "first 5 min",
         "say": ["Confirm sync (multi-device) and sharing, not just blob storage.",
                 "Pin durability, dedup, and bandwidth-efficient sync as the hard goals.",
                 "Agree sync within seconds is acceptable (eventual, not instant)."]},
        {"phase": "High-level design", "time": "next 10 min",
         "say": ["Chunk files and content-address them.",
                 "Dedup via check-then-upload-missing.",
                 "Split metadata (tree/versions/manifests) from block storage."]},
        {"phase": "Deep dive", "time": "next 15 min",
         "say": ["Delta sync with cursors + hash compare.",
                 "Change notification (long-poll/push) and conflict handling (conflicted copies).",
                 "Reference-counted GC and durability."]},
        {"phase": "Wrap-up", "time": "final 5 min",
         "say": ["Map requirements to mechanisms.",
                 "Tradeoffs: chunking scheme, commit ordering, GC safety, conflict policy.",
                 "Extensions: sharing/ACLs, CDN tuning, client-side encryption."]},
    ],

    "levelVariants": [
        {"level": "Junior", "expectations": ["Chunks files and stores them.", "Splits metadata from bytes.", "May miss dedup handshake and conflicts."]},
        {"level": "Senior", "expectations": ["Designs content-addressed dedup and delta sync.", "Orders chunk-upload before metadata-commit.", "Handles change notification + conflicts."]},
        {"level": "Staff", "expectations": ["Reasons about content-defined chunking vs fixed.", "Designs safe reference-counted GC with races in mind.", "Discusses durability (erasure coding), sharing/ACLs, and encryption tradeoffs."]},
    ],

    "followUps": [
        "Fixed-size vs content-defined chunking — when does each win?",
        "How do you safely GC chunks without deleting one an in-flight upload needs?",
        "How would you implement sharing and per-folder ACLs?",
        "How do you support client-side (zero-knowledge) encryption while keeping dedup?",
        "How would you handle a single huge file (100 GB) and its sync efficiently?",
    ],
}

if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
