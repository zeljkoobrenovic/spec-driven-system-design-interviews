Today's Spec-Driven System Design Interview: Dropbox / File Sync — System Design.

File sync looks simple until you stop treating "a file" as the unit of work.

Core lesson: split bytes from meaning. Bytes become immutable, content-addressed chunks; metadata tracks paths, versions, manifests, namespaces, ACLs, cursors, quotas, and conflicts.

The walkthrough moves from whole-file upload/download to chunking, dedup, metadata/block split, delta sync, shared namespaces, notifications, conflicts, GC, and durability repair.

Important boundary: notification is not the source of truth. Push/long poll only wakes a device. Metadata commits and per-namespace change logs are authoritative. Devices pull deltas by cursor, download missing chunks, and reset from a snapshot when a cursor is too old.

At scale: ~100M users, ~50B files, ~5 EB logical data, ~200k upload edits/sec, and hundreds of billions of chunk-index rows. Metadata and block storage should not be the same system.

Technology choices make trade-offs concrete: PostgreSQL/Vitess/CockroachDB/FoundationDB/Spanner for metadata; S3/GCS/Blob Storage/Ceph/MinIO for chunks; DynamoDB/Bigtable/Cassandra/ScyllaDB for indexes; Kafka/Kinesis/Pub/Sub/Event Hubs plus WebSocket/long-poll gateways for change delivery; signed CDN URLs for downloads.

Managed services remove plumbing. They do not remove idempotent commits, version conflicts, commit-time ACL checks, dedup privacy, cursor recovery, refcount drift, or GC safety.

Try the walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#file-sync

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems
