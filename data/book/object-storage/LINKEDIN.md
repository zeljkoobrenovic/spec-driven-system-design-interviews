Today's Spec-Driven System Design Interview: S3-like Object Storage — System Design.

Object storage turns "store a file" into a distributed systems problem: durability math, metadata indexing, hot reads, and repair.

Core lesson: metadata decides whether an object exists; bytes alone are not the source of truth.

The walkthrough moves from one fileserver to split metadata/data planes, replication vs. erasure coding, commit-last writes, multipart upload, scrub/repair/GC, and sharded listing.

The invariant is simple: data can be durable on disk and still invisible until committed metadata points at it. That explains read-after-write, versioning, delete markers, LIST consistency, orphan cleanup, and retries.

At ~10T objects, exabytes, ~300k PUT/s, ~3M GET/s, and ~50k LIST/s, one tier is not enough. The final design uses transactional metadata and a bucket index for control. The data plane handles hot replication, cold erasure coding, signed reads, degraded reconstruction, and repair.

Technology choices shape it: FoundationDB/Spanner/CockroachDB/DynamoDB/Cassandra/ScyllaDB for metadata; Ceph/MinIO/Swift or cloud object stores for data; queues/logs for repair and GC; KMS/Vault for encryption; CDNs for hot reads.

Managed services remove machinery. They do not remove visibility commit order, failure-domain placement, repair lag, index consistency, signed data-plane access, GC safety, or cost-vs-latency tiering.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#object-storage

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems #CloudStorage
