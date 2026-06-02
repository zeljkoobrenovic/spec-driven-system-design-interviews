# Review: WhatsApp / Chat - System Design

Reviewed file: `data/book/whatsapp-chat/interview.json`
Review date: 2026-06-01

## Executive Summary

The latest version is a major improvement over the initial review target and over the first follow-up pass. Most earlier P1 findings are now resolved: capacity math is more precise, API coverage is broader, the data model now supports abuse/privacy/retention, sequence flows were corrected, regional DR semantics were added, technology choices grew to ten concerns, and the final design now includes backpressure signals to ChatSvc, gateways, and the load balancer.

This is now a strong book-level chat-system case. The remaining issues are narrower: central session-registry lease-write math still needs one consistency pass, the API should expose the key-directory and group/admin surfaces implied by the model, and a few renderer/pedagogy choices could be tightened for clarity.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.6 / 5 | Strong architecture and state model; central lease-write assumptions need precision. |
| Production realism | 4.45 / 5 | Good capacity, DR, backpressure, abuse, privacy, and tech-choice coverage; a few workflows remain implicit. |
| Pedagogical flow | 4.55 / 5 | Clear progression and strong traps/flows; step 7 is still dense. |
| Dataset/rendering fit | 4.35 / 5 | References validate cleanly; role-specific sequence participants may not get canonical node annotations. |
| Overall | 4.5 / 5 | Close to reference quality after one focused consistency pass. |

## What Changed Since The Initial Review

- Capacity now has 15 entries, including gateway fleet size, heartbeat observations, registry reads, registry writes, partitioning, fanout amplification, media-plane load, and reconnect storms.
- API coverage grew to 9 entries, including connect/resume, send, group send, receipts, sync, media, typing/presence, and abuse/retention controls.
- The data model grew to 11 entities: conversations, membership, messages, inbox entries, delivery state, cursors, devices, user blocks, rate limits, device keys, and media objects.
- DR is now scoped with single-region-per-conversation, cross-region log replication, near-zero RPO target, minutes-level RTO, owner promotion, and split-brain avoidance.
- Sequence flows for receipts, offline delivery, media, and reconnect now match the gateway/client paths much better.
- Technology choices now cover observability/control, rate limiting, key management, and cross-region DR in addition to gateways, registry, log, queue, push, and media.
- The final design now describes observability-driven backpressure into ChatSvc, gateways, and LB admission control.

## What Works Well

- The teaching arc is strong: polling fails, WebSockets solve push, session routing solves reachability, persist-before-ack solves loss, queues/cursors solve offline sync, fanout extends delivery to groups, and the final step closes presence/media/resilience.
- The correctness model is now credible: scoped idempotency, per-conversation sequence ownership, per-device delivery/read state, per-user inbox entries, and per-device cursors.
- Group fanout is realistic: versioned membership snapshots, auth checks, blocked-user handling, idempotent fanout writes, and fanout-on-read for broadcast scale.
- The dataset now names operational pressure points: registry lookup/read load, local heartbeat observations, lazy lease refresh, fanout lag, queue drain, reconnect admission, and gateway saturation.
- Privacy and abuse are no longer just follow-ups. `device_keys`, `user_blocks`, and `rate_limits` give those requirements concrete state.
- Structural references are clean: high-level nodes/links, final-design references, `satisfies` steps, pattern steps, technology-choice steps, and icon fields all validate.

## Highest-Impact Issues

### 1. Registry lease-write math still needs reconciliation

The capacity section correctly separates heartbeat observations from central registry writes. However, the write estimate still has an internal tension: 300M devices with a 90s TTL implies at least about 3.3M lease refreshes/sec if every device has a central expiring entry. The current note says central writes are about 0.5-1M/sec while also saying gateways refresh lazily once per 30-60s per device, which would actually be 5-10M/sec.

Why it matters: the session registry is the hottest stateful component in the design. If its write budget is understated, the design can look more scalable than it is.

Concrete fix:

- Pick one explicit model:
  - Per-device central TTL entries: use the true write rate (`devices / refresh_interval`) and shard aggressively.
  - Per-gateway aggregate leases plus local device maps: central writes are low, but online routing needs a second hop to the gateway or a gateway-owned user/device index.
  - Hybrid: central user->gateway/device-set updated only on connect/disconnect, gateway-local heartbeats drive presence until lease expiry.
- Align the TTL, refresh interval, and write-rate math in one sentence.
- Update `capacityDiagram` so `Hb --> Reg` does not visually imply every heartbeat writes the central registry. Show "local heartbeat" and "lazy lease refresh" separately.

### 2. API now covers more behavior, but key and admin surfaces are still implicit

The data model includes `device_keys`, `user_blocks`, `rate_limits`, and versioned membership, but the API only partially exposes the operational workflows around them.

Why it matters: the dataset now claims privacy, abuse controls, and group authorization as requirements. Those claims are credible in the model, but interview candidates should see how clients/services interact with that state.

Concrete fix:

- Add a key-directory API: register device keys, fetch peer prekeys, rotate/revoke a device key.
- Add group/admin APIs or frames: add/remove member, promote admin, leave group, and how those increment `membership_version`.
- Add explicit rate-limit failure behavior for normal `send_message`, not only group send.
- Clarify whether `DELETE /v1/messages/{id}` is sender-only, admin-moderated, or available to any participant, and how tombstones sync to devices.

### 3. Step 7 is accurate but too dense for a flagship walkthrough

Step 7 now carries presence, typing, media, gateway crash recovery, reconnect storms, regional gateway failover, conversation-owner failover, E2E framing, and observability/backpressure.

Why it matters: the content is good, but it compresses several senior-level design topics into one step. In an interview walkthrough, this can make the final act feel like a checklist instead of a sequence of design decisions.

Concrete fix:

- Keep the sidebar step count if desired, but split the step content into clearer sub-sections:
  - Presence and typing fanout
  - Media plane
  - Gateway reconnect and admission control
  - Regional DR and conversation ownership
  - Privacy/key directory
- Or make `scale-presence` a parent with sub-steps if the book case can support a longer walkthrough.

### 4. Role-specific sequence participants may miss canonical node annotation

Several sequence diagrams use role-specific participants such as `RecipientClient`, `SenderGateway`, and `RecipientGateway`. This is semantically useful, but those IDs are not high-level architecture node IDs. The renderer can still render the sequence, but participant type annotation/highlight inheritance may not map as cleanly to canonical `Client` and `Gateway`.

Why it matters: this repo's sequence highlighting/type annotation works best when participants map to canonical node IDs or a clear alias convention. Role-specific IDs are useful for readability, but they should not quietly lose type metadata.

Concrete fix:

- If renderer support already handles this pattern, document the convention in `AGENTS.md`/`CLAUDE.md`.
- Otherwise add a schema convention such as `{ id: "RecipientClient", node: "Client", label: "Recipient Device" }` and update the renderer to use `node` for metadata while preserving a unique Mermaid alias.
- At minimum, keep highlights explicit on canonical participants (`ChatSvc`, `MsgDB`, `Media`, `Session`, `MsgQ`) as the dataset currently does.

### 5. Final design is comprehensive but visually crowded

The final design now includes all major components and control-plane links. That is good, but it is approaching the point where the final diagram may be harder to scan than the step diagrams.

Concrete fix:

- Keep the current full final design, but consider adding optional view filters or grouped captions for "delivery path", "control plane", and "media path".
- If adding more nodes for key directory or rate limits, avoid putting every supporting store into the main final diagram. Consider showing them in data model/API sections instead.

## System Design Soundness

### Requirements

The requirements are now realistic for a WhatsApp-style case. Functional requirements cover real-time delivery, offline buffering, groups, receipts, presence, multi-device sync, media, and abuse controls. Nonfunctional requirements now include privacy, regional DR, retention, and deletion.

Remaining issue: the privacy and retention requirements are now state-backed, but their workflows should be one click more explicit in the API and step text.

### Capacity

The capacity section is now one of the strongest parts of the dataset. It correctly distinguishes original sends, delivery events after fanout, registry reads, local heartbeat observations, central lease writes, queue storage, media bandwidth, and reconnect storms.

The one weak spot is the central lease-write estimate. Fixing that math will remove the last major credibility gap.

### API

The API is strong enough to support the main architecture. The important message-path fields are present: `conversationId`, `senderDeviceId`, `clientMsgId`, `conversationSeq`, `membershipVersion`, cursors, resume tokens, media IDs, and receipt frames.

Recommended refinements:

- Add key-directory operations.
- Add group membership/admin operations.
- Add rate-limit behavior to the base send path.
- Consider adding sequence diagrams for abuse/deletion and key registration if those remain first-class requirements.

### Data Model

The data model now supports the promised behavior. The addition of `user_blocks`, `rate_limits`, `device_keys`, `deleted_at`, `expires_at`, and `sender_key_id` resolves a large part of the previous review.

Remaining refinements:

- Decide whether `device_keys` should be renamed without parentheses for cleaner rendering, even if the ER renderer sanitizes it.
- Add `deleted_by` or `delete_scope` if delete semantics matter.
- Add a retention/lifecycle state to `media_objects` beyond `expires_at` if account deletion needs auditable cleanup.

### Architecture

The architecture is coherent. The `GroupDB` label is now corrected to "Conversation Membership Store", and observability/backpressure now feeds ChatSvc, Gateway, and LB. The final design explains log-vs-inbox ownership, sender other-device sync, membership snapshots, media isolation, and regional ownership.

Remaining refinement: decide whether key directory and rate limit stores belong in architecture diagrams or only in the data/API sections.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Poll the Server for New Messages

This step is strong. The polling arithmetic is concrete and the diagram now matches HTTP polling rather than WSS.

### Step 2: Persistent Connections via WebSocket Gateways

The step is clear and still the right foundation. Add one sentence about graceful connection draining during deploys if you want to cover normal operations, not just crashes.

### Step 3: Route a Message to the Recipient's Connection

This step is strong on multi-device routing, TTL leases, stale-session fallback, and sender other-device sync. The only improvement is aligning the exact registry lease model with the capacity section.

### Step 4: Reliable, Ordered, Idempotent Delivery

This is now a strong correctness step. The receipt flow includes sender and recipient clients, and the shard-unavailable failure drill is valuable.

Remaining polish: mention what happens if the conversation shard becomes hot because a large group is extremely active. The group step covers fanout scale, but not sequence-allocation hot spots.

### Step 5: Offline Delivery and History Sync

The per-user inbox plus per-device cursor model is now clear. The data-model note explicitly says the inbox is an optimization for wake/drain, not the only source of per-device delivery.

### Step 6: Group Messaging and Fanout

This step is production-realistic now. It covers membership versioning, auth, blocks, partial fanout retries, and fanout-on-read for broadcast scale.

Remaining polish: add a tiny note that membership-version history must be retained long enough to evaluate old message visibility and deletion/account-removal workflows.

### Step 7: Presence, Media, and Gateway Resilience

This step is technically strong but dense. It now covers the right concerns; the improvement is presentation, not substance.

## Final Design Review

The final design now integrates nearly all design decisions:

- WebSocket gateways and connection LB.
- Lease-based session/presence registry.
- Durable message log with per-conversation ownership.
- Per-user inbox queue and per-device cursors.
- Fanout with versioned membership.
- Push wakeups.
- Media plane.
- Observability/control plane.
- Regional DR and ownership failover.
- Ciphertext payload routing.

This is close to complete. The remaining open choice is whether to keep key directory/rate limits/data-retention stores out of the main architecture diagram for clarity or add a secondary security/abuse view.

## Concept Introduction and Learning Flow

The concept progression is now strong and just-in-time:

- WebSocket gateway
- Session registry
- Session lease / heartbeat TTL
- Idempotent send
- Per-conversation sequence
- Device sync cursor
- Inbox entry
- Membership snapshot
- Heartbeat presence
- Reconnect storm / jittered backoff

Potential additions:

- Conversation ownership region
- Key directory / prekey bundle
- Tombstone / retention lifecycle
- Rate-limit bucket

## Step-to-Final-Design Coherence

Coherence is high. Each step introduces components that appear in the final design, and the final design now reflects the operational additions from the later edits.

The only subtle gap is that abuse/privacy/retention are now data-model/API concerns more than diagram concerns. That is acceptable, but the review should remain conscious that they are not first-class nodes in the final diagram.

## Realism Compared With Production Systems

This is now production-realistic enough for a serious system-design interview. It covers the major hard problems: socket fanout, registry scale, multi-device sync, dedup, ordering, offline delivery, group fanout, DR, media offload, abuse controls, privacy, and observability.

Residual realism gaps:

- Central lease-refresh math must be exact.
- Hot conversation/group sequence ownership needs a sentence.
- Key-directory APIs and lifecycle operations are still implicit.
- Step 7 should be easier to scan.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- `highLevelArchitecture` node IDs, step `view.nodes`, step `view.links`, final-design references, `satisfies[*].steps[*]`, pattern step links, technology-choice step links, and icon fields validate cleanly.
- Canonical node types used here are valid, including `observability`.
- Technology-choice chips all have icon fields assigned.
- `assets.icon` points to `icon.png`, and the source directory contains `icon.png`.
- Sequence diagrams use some role-specific synthetic participants. They render, but may not receive canonical node metadata unless the renderer supports a role-to-node mapping convention.
- `docs/book/data/whatsapp-chat/interview.json` is modified alongside the source dataset, which is consistent with a rebuild after dataset edits. This `REVIEW.md` remains source-only and should not be copied into docs.

## Recommended Edits, Prioritized

### P1: Fix central registry lease-write semantics

- Choose per-device TTL, per-gateway aggregate lease, or hybrid ownership explicitly.
- Make TTL, refresh interval, and write-rate math agree.
- Update the capacity diagram to distinguish local heartbeat observations from central lease writes.

### P2: Add missing workflow APIs

- Add device-key registration/fetch/rotation APIs.
- Add group membership/admin APIs.
- Add normal-send rate-limit behavior.
- Clarify message/media/account deletion semantics.

### P2: Improve renderer-facing sequence metadata

- Document or implement a role-specific participant mapping to canonical nodes.
- Keep role labels for readability, but preserve canonical node metadata for type annotations.

### P3: Pedagogy polish

- Split Step 7 into sub-sections or sub-steps.
- Add one note on graceful gateway draining during deploys.
- Add one note on hot conversation/group sequence ownership.
- Consider a secondary security/abuse view instead of crowding the final diagram.

## What Not To Change

- Keep the overall step order.
- Keep thin gateways and ChatSvc-owned delivery semantics.
- Keep session registry lookup as the default routing design.
- Keep at-least-once plus idempotent send/apply framing.
- Keep per-user inbox entries plus per-device cursors.
- Keep membership-version fanout and fanout-on-read for broadcast scale.
- Keep the expanded technology choices.

## Bottom Line

The current `whatsapp-chat` dataset is close to reference quality. The latest edits resolved nearly all substantial issues from the initial review. The next pass should be small but precise: make the central registry lease model mathematically consistent, expose the key/admin/lifecycle APIs implied by the data model, and clean up dense or renderer-sensitive presentation details.
