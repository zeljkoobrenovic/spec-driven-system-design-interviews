# Review: Slack / Discord - System Design

Reviewed file: `data/book/slack/interview.json`
Review date: 2026-06-04

## Executive Summary

The recent changes materially improve this dataset. The earlier highest-impact issues around missing capacity math, absent buffered fanout, missing history/membership APIs, permission revocation, and diagram endpoint mismatches are now mostly addressed. The interview is now a strong, coherent Slack/Discord walkthrough with a credible scaled fanout path.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong core architecture with queue-backed fanout, current-membership search, and reconnect/catch-up behavior. Remaining gaps are mostly consistency and operational precision. |
| Production realism | 4/5 | Much stronger after adding numeric capacity, revocation handling, bottlenecks, and failure drills. Needs a clearer search API/service boundary and queue semantics. |
| Pedagogical flow | 4/5 | Steps still build naturally and now expose more realistic failure modes. |
| Dataset/rendering fit | 4/5 | JSON and option validation pass; stricter view endpoint checks are clean. One API sequence is now stale relative to the architecture. |

## What Changed Since The Previous Review

- Added `FanoutQueue` as a canonical architecture node and routed `Channel -> FanoutQueue -> Fanout` in the high-level links and final design (`interview.json:65`, `interview.json:174`).
- Replaced qualitative capacity with concrete workload numbers: sockets, messages/sec, fanout pushes/sec, storage/day, search QPS, and reconnect-storm assumptions (`interview.json:312`).
- Expanded the API from 3 entries to 8 entries, adding membership change, history catch-up, unread cursor, and presence/typing events (`interview.json:349`).
- Expanded the data model with `client_msg_id`, `channels`, membership status/versioning, and reactions (`interview.json:507`).
- Fixed the earlier Step 3/Step 4 diagram endpoint issues; the stricter endpoint check now reports no missing link endpoints.
- Added search revocation traps and scale failure drills for private-channel removal, queue lag, and reconnect storms (`interview.json:1406`, `interview.json:1722`).

## What Works Well

- The interview keeps the right story for team chat: workspaces/channels and ACLs first, then live fanout, durable ordered history, scoped search, ephemeral presence, and finally scale.
- Queue-backed fanout is now represented in prose, diagrams, final design, and Step 7 bottleneck handling.
- Capacity is now actionable enough to support trade-off discussion. `~50K msg/sec`, `~1-2M pushes/sec`, a `50K` member channel, and reconnect-storm assumptions give candidates real numbers to reason with.
- The revocation handling is much better. Membership versioning, live subscription invalidation, and query-time filtering are now explicit.
- The Step 7 bottlenecks and failure drills are realistic and useful for senior/staff-level discussion.
- The dataset references resolve cleanly: `satisfies` step links, pattern step links, step pattern names, and probe links all resolve.

## Highest-Impact Issues

### 1. The post-message API sequence still bypasses the fanout queue

The architecture now says fanout is enqueued after the durable commit: `Channel -> FanoutQueue -> Fanout` (`interview.json:174-184`). Step 3's structured flow also uses `FanoutQueue` (`interview.json:999-1038`), and the final design includes the queue (`interview.json:1743-1779`).

But the top-level `POST /v1/channels/{id}/messages` API sequence still has participants `Client`, `Channel`, `Membership`, `ChannelDB`, and `Fanout`, then sends `Channel -> Fanout` directly (`interview.json:402-454`). That is now stale and teaches a different write path from the rest of the dataset.

Concrete fix: add `FanoutQueue` to that API sequence and change the final send path to `Channel -> FanoutQueue` then `FanoutQueue -> Fanout`. Optionally label the client ack as happening after durable commit and enqueue, not after all fanout pushes complete.

### 2. Search enforcement is described, but the architecture still shows the client querying the index directly

The search text now says each query resolves current membership and filters results (`interview.json:1230-1232`). The flow also asks `Client -> Membership` for accessible channels before querying the index (`interview.json:1457-1467`).

However, the high-level architecture and final design still have a direct `Client -> SearchIdx` link (`interview.json:222-226`, `interview.json:1774-1777`), and there is no `SearchService` node. In the Step 5 view, the membership link is `Channel -> Membership`, not a query-time search authorization path (`interview.json:1234-1248`). That makes the diagram less precise than the prose: a real API/service layer should enforce ACLs, pagination, ranking, audit, and rate limits before touching the search index.

Concrete fix: add a `SearchService` node, replace `client-search` with `Client -> SearchService`, add `SearchService -> Membership` for ACL scope, and `SearchService -> SearchIdx` for the filtered query. If adding a new node is too much, at least relabel the direct index link so it is clear the client is calling a search API, not the index itself.

### 3. Threads/reactions are partly scoped but not fully tied to API behavior

The requirement now calls threads and reactions "message extensions" (`interview.json:296-302`), which is a reasonable scope reduction. The data model includes `thread_id` and a `reactions` table (`interview.json:533-616`).

The remaining gap is that there is no API for adding/removing a reaction, listing thread replies, or posting a reply to a thread. That is acceptable if they remain follow-ups, but the dataset should make that boundary explicit in the requirements or interview script.

Concrete fix: either move threads/reactions entirely to follow-ups/extensions, or add compact API entries for `POST /messages/{id}/reactions`, `DELETE /messages/{id}/reactions/{emoji}`, and `GET /messages/{id}/thread`.

### 4. Queue semantics are named but not specified enough for the main scaling mechanism

Step 7 now describes queue depth, backpressure, pull-mode degradation, and a dead-letter path (`interview.json:1650-1653`, `interview.json:1700-1708`). That is a big improvement. The architecture still represents only a generic `FanoutQueue`; it does not say whether fanout work is partitioned by channel, whether per-channel order is preserved, how poison messages are isolated, or how workers avoid a single giant channel starving small channels.

Concrete fix: add one short note or bottleneck about queue partitioning/fairness: keyed by channel, per-channel ordering where needed, worker pools that prioritize small/interactive channels, and DLQ/retry policy that does not block the channel forever.

### 5. Capacity is much better, but storage and network multipliers are still understated

The capacity section is now useful (`interview.json:312-347`). The `~4TB/day` storage estimate is a good raw baseline, but production storage and index cost will be multiplied by replication, search index overhead, attachments/files, retention windows, and compliance/deletion workflows. Similarly, `~1-2M pushes/sec` should connect to gateway egress and per-gateway fanout limits.

Concrete fix: add one line that treats current numbers as logical workload, then notes physical cost multipliers: replication factor, index expansion, attachment storage, gateway egress, and retention/delete policies.

## System Design Soundness

The core design is now sound for a senior-level interview. The message write path has the right intended sequence: permission check, idempotent durable write with per-channel sequence, enqueue fanout, drain with scalable workers, push to online gateways, and let offline users catch up from history. `client_msg_id` in the model closes the previous idempotency gap.

Search is directionally sound: one shared index plus query-time permission filtering is a credible default because revocation can take effect without rebuilding per-user indexes. The remaining issue is representation: the diagrams should show the service that enforces the filter instead of a direct client-to-index edge.

The scale story is strong: fanout queue depth, pull-mode degradation, reconnect catch-up, rebuildable registry, and private-channel revocation are all now present. The next level of rigor would specify queue partitioning, fairness, retry/DLQ behavior, and observability thresholds.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Channel, Poll for Messages, No Permissions

Still a good baseline. It cleanly motivates both permissions and push fanout. The current capacity section now gives enough numbers for this step to feel less abstract.

### Step 2: Workspaces, Channels, and Permissions

The step remains correctly placed before delivery mechanics. The data model now supports channels and membership versioning, so the teaching story is better grounded.

Improvement: if workspace-level tenancy is important, add a tiny `workspaces` model entry or state explicitly that `workspace_id` on `channels` is sufficient for this scoped interview.

### Step 3: Channel Fanout over Live Connections

This step is now much stronger because `FanoutQueue` appears in the main view, default option, hybrid option, and flow. The duplicate-tolerant retry wording is useful.

Improvement: update the top-level API sequence to match this step's flow. Right now Step 3 is correct, while `api[POST /messages]` is stale.

### Step 4: Ordered Durable History

The step is solid. It now has the supporting APIs for history catch-up and unread cursor, and the model has `client_msg_id` for dedup.

Improvement: add one sentence about sequence allocation under hot channels: single-writer/channel partition, log offset, or sequence allocator. The options cover this, but the chosen default could be more operationally explicit.

### Step 5: Permission-Scoped Search

The recent traps add exactly the right teaching points: do not bake ACLs into the index, and do not promise instant search. The revocation story is much better.

Improvement: make the search architecture match the prose by adding a search service or at least a query-time membership edge from the search path.

### Step 6: Presence and Typing

The step is appropriately scoped as ephemeral and best-effort. The WebSocket event API adds concrete shape.

Improvement: presence still lacks explicit heartbeat interval, TTL refresh behavior, and fanout throttling values. That is polish, not a core issue.

### Step 7: Scaling Large Channels and Gateways

This is now a strong closing step. The bottlenecks and failure drills cover the right operational concerns: queue lag, gateway crashes, reconnect storms, revocation, and large-channel pull-mode degradation.

Improvement: add queue partitioning/fairness details so the main scaling mechanism is not just "queue plus workers."

## Final Design Review

The final design now integrates the main steps well. It includes `FanoutQueue`, idempotent durable writes, current-membership search filtering, subscription invalidation on membership changes, large-channel pull-mode degradation, and reconnect/catch-up behavior (`interview.json:1741-1779`).

The main final-design gap is the search boundary. The final diagram still shows `Client -> SearchIdx`; a `SearchService` would make the final design more production-realistic and align the diagram with the ACL-filtering story.

## Concept Introduction and Learning Flow

Concept staging is good. The newly added "Permission revocation under distributed state" pattern is valuable because it connects membership, search, subscription routing, stale caches, and gateway state.

The concept flow would be even stronger if queue/backpressure had a named pattern entry, for example "Buffered fanout with per-channel fairness," tied to Step 7.

## Step-to-Final-Design Coherence

Most steps now build cleanly into the final design. Step 7's queue-backed scaling story is now represented in the final design, fixing the previous coherence gap.

The remaining mismatch is localized: the top-level post-message API sequence still uses the older direct fanout path, while the step flow and final design use `FanoutQueue`.

## Realism Compared With Production Systems

The dataset is now much closer to production realism. It covers idempotency, durable ordering, queue-backed fanout, async indexing, current ACL filters, revocation, reconnect storms, and pull-mode degradation.

Remaining production details worth adding:

- search API/service layer, rate limits, audit, and permission-filter failure metrics;
- queue partitioning/fairness, retry limits, DLQ behavior, and fanout lag SLOs;
- physical storage/index/network multipliers beyond raw message volume;
- workspace/user lifecycle and channel creation if the scope includes full workspace management;
- retention, deletion, legal hold, and private-channel audit behavior;
- concrete heartbeat/TTL/throttle values for presence and typing.

## Dataset and Renderer-Facing Observations

- JSON validation passes: `python3 -c "import json; json.load(open('data/book/slack/interview.json'))"`.
- Option validation passes: `python3 _scripts/validate_options.py data/book/slack/interview.json`.
- Stricter `view.links` endpoint checks now pass for steps, options, and final design.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, step `patterns[]`, and step `probeLinks[]` resolve.
- `data/book/slack/interview.json` and `docs/book/data/slack/interview.json` are both modified in the working tree, suggesting the built docs copy has been regenerated or edited alongside the source.

## Recommended Edits, Prioritized

### P1: Align the post-message API sequence with `FanoutQueue`

Patch `POST /v1/channels/{id}/messages` so the API sequence includes `FanoutQueue` and shows enqueue-after-commit before fanout workers drain.

### P1: Add a search service boundary

Add `SearchService` to the high-level architecture and final design, with links `Client -> SearchService`, `SearchService -> Membership`, and `SearchService -> SearchIdx`.

### P2: Clarify threads/reactions scope

Either keep them as explicit follow-up extensions, or add compact reaction/thread APIs so the requirement is fully supported.

### P2: Add queue partitioning/fairness semantics

Add a short note, bottleneck, or concept for per-channel queue partitioning, worker fairness, retries, and DLQ behavior.

### P3: Add capacity multipliers

Annotate the current logical numbers with physical multipliers for replication, index expansion, attachment storage, retention, and gateway egress.

## What Not To Change

- Keep permissions before fanout.
- Keep presence separate from the durable message path.
- Keep query-time search permission filtering as the default.
- Keep push vs pull/hybrid as the main large-channel trade-off.
- Keep the new revocation failure drill; it is one of the strongest recent additions.

## Bottom Line

The recent changes move this from a good outline to a credible interview dataset. The remaining high-value work is narrow: make the API sequence match the new queue-backed architecture, add a search service boundary, and add enough queue/search operational detail to make the scaled design feel fully production-grade.
