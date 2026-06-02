# Review: Collaborative Editing (Google Docs) - System Design

Reviewed file: `data/book/collab-editing/interview.json`
Review date: 2026-06-02

## Executive Summary

This dataset has improved materially since the first review and again since the previous review update. The original high-impact gaps are now addressed: capacity is numeric and distribution-aware, op delivery is idempotent with durable `clientOpId`, ownership failover is fenced by `owner_epoch`, the target conflict model is explicitly OT, offline reconnect has a concrete protocol, presence/offline diagram labels now match the intended local/in-memory state, `satisfies` is complete, and `technologyChoices` includes observability.

The case is now a strong production-realistic teaching walkthrough. It does not just name collaborative-editing concepts; it shows the invariants that keep the system correct under lost acks, reconnects, stale owners, snapshot failures, slow clients, and permission changes.

Remaining issues are mostly staff-level polish: final-design/runbook guardrails for slow clients and hot docs could be surfaced more prominently, version-history retention/deletion policy is still implicit, and several technology chips still use generic fallback icons.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.7/5 | Correct target architecture with explicit invariants; remaining work is operational precision. |
| Production realism | 4.5/5 | Strong retry, fencing, reconnect, snapshot, and observability coverage. |
| Pedagogical flow | 4.7/5 | Concepts are introduced where later steps need them. |
| Dataset/rendering fit | 4.8/5 | Cross-references and diagrams validate cleanly; only visual/icon polish remains. |
| Overall | 4.7/5 | A strong book-quality case with only targeted refinements left. |

## Changes Since The First Review

Resolved:

- Capacity now distinguishes hot-doc, typical, and p95 active-doc behavior (`data/book/collab-editing/interview.json:249`, `data/book/collab-editing/interview.json:261`, `data/book/collab-editing/interview.json:266`).
- Storage math is now framed as hot-doc active-hour throughput rather than an ambiguous day estimate (`data/book/collab-editing/interview.json:296`, `data/book/collab-editing/interview.json:301`).
- `send-op` now uses durable `clientOpId` plus `clientSeq`, re-checks ACL/owner status, and explains that owner epoch is attached server-side (`data/book/collab-editing/interview.json:381`).
- The `operations` model now has stable `client_id`, durable `client_op_id`, `session_id`, `client_seq`, and a unique `(doc_id, client_id, client_op_id)` constraint (`data/book/collab-editing/interview.json:512`, `data/book/collab-editing/interview.json:546`, `data/book/collab-editing/interview.json:566`).
- The optimistic client step now says the pending queue and session identity are persisted before local acceptance (`data/book/collab-editing/interview.json:754`).
- The final design now commits to OT and durable client-op dedupe that survives reload/restart/offline gaps (`data/book/collab-editing/interview.json:2079`).
- Presence is now labelled `In-Memory Presence`, not `Presence Service` (`data/book/collab-editing/interview.json:56`).
- Offline buffering is now labelled `Client Local Pending Ops` and typed as a client-boundary component (`data/book/collab-editing/interview.json:96`).
- The offline step now includes editing-quality SLIs and collaboration-specific runbooks (`data/book/collab-editing/interview.json:1921`, `data/book/collab-editing/interview.json:1928`).
- `technologyChoices` now includes `Observability and incident response` (`data/book/collab-editing/interview.json:2470`).

## What Works Well

- The central invariants are clear: one active owner epoch per doc, durable append before ack, idempotent client op identity, clients converge by replaying the accepted op set under server order, and presence is best-effort.
- The capacity section now teaches why single-owner ordering is plausible for bounded hot docs while avoiding the misleading assumption that every active doc is hot.
- The API and data model now support the promised behavior: reconnect, stale-base rejection, owner-moved rejection, permission-denied rejection, session-independent dedupe, snapshot versioning, and owner fencing.
- The OT/CRDT choice is no longer ambiguous. OT is the target for the server-centric case; CRDT remains the alternative for offline-first/P2P.
- The offline step is now a real production flow: missed-op catch-up, client-side rebase, durable dedupe, stale-tail snapshot resync, ACL re-check, and slow-client backpressure.
- The renderer-facing model is clean: links, participants, `satisfies` slugs, probe links, and pattern links validate cleanly against the source dataset.

## Highest-Impact Remaining Issues

### 1. Slow-client and hot-doc operations are present, but not fully tied to final design

The offline step now includes slow-client backpressure and editing-quality SLIs (`data/book/collab-editing/interview.json:1921`). The final design does not yet summarize those operational guardrails.

Why it matters: the final design is the snapshot a candidate will remember. It should include the operational limits that keep the one-owner model healthy under load.

Concrete fix:

- Add one sentence to `finalDesign.description`: cap per-connection send buffers, coalesce/drop presence first, then force snapshot resync for clients that fall too far behind.
- Add hot-doc protection: enforce the 50-editor cap, batch keystrokes, shed presence first, and alert on broadcast lag.
- Make the runbook examples visible in wrap-up or follow-ups, not only inside the offline step concepts.

### 2. Version-history retention is good, but privacy/deletion policy is still implicit

The durability step now explains archived snapshots plus cold op streams for version restore (`data/book/collab-editing/interview.json:1501`). That resolves the earlier restore-path issue. What remains implicit is how long history is retained and how deletion/privacy requests affect archived snapshots.

Why it matters: collaborative documents can contain sensitive content. A production design should not make version history indefinite by accident.

Concrete fix:

- Add a short retention-policy note for archived snapshots and cold op streams.
- Mention hard delete / legal retention / restore-window tradeoffs.
- Add a follow-up asking how to delete or redact a document from archived history.

### 3. Technology choices are useful, but many chips still use the generic fallback icon

The technology choices are now a good addition, especially observability. Many chips still use `assets/tech-icons/tech.png`, including common services and libraries. This is not a correctness issue, but it makes the technology section less polished than the stronger datasets.

Concrete fix:

- Add icon mappings for high-value missing terms such as AppSync, Kinesis, MSK, Pub/Sub, Spanner, S3, CloudWatch, ShareDB, Yjs, Automerge, and Azure Web PubSub where assets are available.
- Re-run the tech icon assignment script after updating `_media/index.yaml`.

## System Design Soundness

### Requirements

The requirements cover the correct product surface: multi-user editing, real-time visibility, convergence, presence, offline edits, version history, low-latency local feedback, durability, scale, and brief outage tolerance. The `satisfies` section now maps scale and availability explicitly, so the requirement-to-design coverage is coherent.

One wording improvement remains: "All clients converge on an identical final document regardless of edit order" would be more precise as "all clients converge for the same accepted operation set under the server-assigned order and transform rules." The target is OT over a server order, not arbitrary order independence.

### Capacity

This section is now strong. It separates:

- Hot-doc cap: about 50 editors.
- Typical active doc: about 1-3 editors.
- p95 active doc: about 8-10 editors.
- Hot-doc edit fanout: about 12.5K messages/sec.
- Hot-doc presence fanout: about 25K messages/sec.
- Hot-doc op-log writes: about 250 ops/sec.
- Hot-doc raw op throughput: about 25 KB/sec.
- Hot-doc active-hour storage: about 90 MB before overhead.

That is enough to justify one owning server per active doc and to explain why presence stays outside the durable path.

### API

The API now fits the architecture:

- `connect` returns snapshot/tail/head/session/owner/ACL metadata.
- `send-op` is idempotent, ACL-checked, owner-epoch-safe, and explicit about rejection cases.
- `presence-update` is best-effort and version-anchored.
- `reconnect` covers missed ops, pending ops, durable dedupe, and snapshot resync.

This resolves the first review's API concerns. The only small polish item is to include `clientOpId` in the successful ack response alongside `clientSeq`, because the dedupe key is now client-op-scoped.

### Data Model

The `operations`, `snapshots`, and `documents` entities now support the promised behavior. The `operations` table has the durable client-op dedupe key; `snapshots` has format/checksum metadata; `documents` has ownership lease and ACL versioning.

The model is intentionally compact and appropriate for this case. Additional entities are optional: a `sessions` table for active collaborators, an archived-history table, or a lease-event audit log would add realism but are not required for the teaching target.

### Architecture

The single-owner-per-document model is now credible because ownership is fenced. The final design states the target architecture and invariants clearly.

The remaining architecture refinements are operational: make slow-client eviction/resync thresholds visible in the final design and clarify retention/deletion policy for archived history.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Last-Write-Wins Whole-Document Save

Still a strong opening. It exposes lost updates and now explains why the discarded blob-style PUT is not listed in the final API section.

### Step 2: Optimistic Local Editing

This step is now excellent. It introduces pending ops, `clientSeq`, durable `clientOpId`, persisted local queue, and rebase before later steps depend on them.

### Step 3: One Authoritative Order per Document

The step now teaches the real subtlety: one owner is only correct with fencing. The concepts, trap, failover sequence, TTL/renewal example, and false-failover handling are strong.

### Step 4: Conflict Resolution: OT vs CRDT

The OT target choice is clear, and the added delete-vs-insert / delete-vs-delete examples make the OT difficulty concrete. This is a good senior-level explanation.

### Step 4a: Choosing Between OT and CRDT

This sub-step remains useful because it reinforces the target choice and preserves CRDT as a serious alternative rather than a strawman.

### Step 5: Durability: Snapshots + Op Log

This step now covers persist-before-ack, idempotent append, snapshot checksums, partial snapshot failure, retained history, and cold-history restore after compaction. It is strong.

### Step 6: Presence: Cursors and Selections

The labels and captions now match the target design: in-memory, best-effort presence on the doc server. This resolves the previous visual mismatch.

### Step 7: Offline Editing and Reconnection

This is now one of the strongest steps. It covers client-local pending ops, durable client-op dedupe, catch-up, rebase, snapshot resync, permission re-check, slow-client handling, SLIs, and runbooks.

Remaining improvement: move a short operational summary from this step into the final design or wrap-up, since it is easy for readers to miss.

## Final Design Review

The final design is now coherent and implementation-aware:

- Single owning doc server per document.
- Operational Transformation as the target conflict model.
- Durable op log with persist-before-ack.
- Session-independent idempotency via `(doc_id, client_id, client_op_id)`.
- Owner-epoch fencing.
- Snapshot + tail recovery.
- In-memory best-effort presence.
- Client-local offline buffering and reconnect catch-up/resync.
- CRDT as the alternative for offline-first/P2P.

This is a strong final answer. The only thing I would add is a compact operational sentence covering slow-client resync and hot-doc presence shedding, since those details currently live deeper in the offline step.

## Concept Introduction and Learning Flow

The dataset now stages concepts well:

- Pending queue and durable client-op identity in optimistic editing.
- Owner lease/fencing in ordering.
- OT target choice and tricky transforms in conflict resolution.
- Idempotent append and snapshot consistency in durability.
- Presence as ephemeral state.
- Reconnect, SLIs, and runbooks in offline.

This is now suitable for senior/staff interview prep because the correctness mechanisms are not bolted on at the end; they are introduced when the candidate needs them.

## Step-to-Final-Design Coherence

Coherence is strong. The final design reflects every major step and no longer leaves a gap between the walkthrough and target architecture.

Remaining coherence polish:

- Put slow-client/hot-doc operational guardrails into `finalDesign.description`.
- Mention retention/deletion policy for archived snapshots and cold op streams.

## Realism Compared With Production Systems

The dataset is now production-realistic for interview depth. It covers:

- Lost updates.
- Optimistic local apply.
- Total ordering.
- OT/CRDT tradeoff.
- Idempotent retries.
- Lost acks.
- Owner fencing.
- Snapshot consistency.
- Offline replay.
- Permission revocation while offline.
- Presence throttling.
- Slow-client backpressure.
- Observability signals.

The remaining realism gaps are about operations and product policy, not core architecture: retention/deletion policy, technology icon polish, and making hot-doc incident handling more visible in the final design.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- Source and generated `docs/book/data/collab-editing/interview.json` match.
- Step, option, and final-design links do not reference endpoints missing from their visible node sets.
- API and step sequence participants resolve.
- `satisfies[*].steps[*]` slugs resolve to real steps.
- `probeLinks` resolve to `toProbeFurther.links`.
- Step `patterns` resolve to dataset-level `patterns`.
- The `ot-vs-crdt` sub-step parent resolves to `conflict`.

Renderer/content polish:

- Many `technologyChoices` chips use the generic `tech.png` fallback. This is harmless but worth improving for a book-quality page.
- Optional generated AI visuals/comics are absent. That is not a correctness issue.

## Recommended Edits, Prioritized

### P1: Add final operational precision

- Add slow-client/hot-doc guardrails to the final design summary.
- Add retention/deletion policy for archived snapshots and cold op streams.

### P2: Polish technology and visuals

- Replace generic `tech.png` mappings for common technologies where icons exist.
- Consider generated AI visuals or an explainer comic if this case should match more visual flagship datasets.

### P3: Add one more follow-up

- Add a follow-up asking how privacy deletion interacts with archived snapshots and version history.

## What Not To Change

- Keep the current step order.
- Keep single owner per document as the target ordering model.
- Keep OT as the target and CRDT as the alternative.
- Keep durable client-op dedupe.
- Keep presence out of the op log.
- Keep offline replay as catch-up + rebase + idempotent resubmit.
- Keep the capacity distribution rows; they are now one of the dataset's strengths.

## Bottom Line

The recent changes address the first review's major concerns. This is now a strong collaborative-editing system design case with credible correctness and production behavior. The next round should focus on final polish: hot-doc operations in the final design, retention/deletion policy, and technology icon quality.
