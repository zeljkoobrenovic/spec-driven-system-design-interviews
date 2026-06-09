# Review: Ad-Click / Analytics Pipeline - System Design

Reviewed file: `data/book/analytics-pipeline/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent strengthening pass materially improved this interview. The case now has quantitative capacity notes, a richer event contract, explicit accepted-event durability, DLQ/quarantine handling, event-time and watermark language, bounded dedup semantics, real-time click-state attribution, versioned rollups, and a clearer provisional-vs-settled serving contract.

It is now a strong book-grade walkthrough. The remaining issues are narrower but still important: one capacity calculation is arithmetically inconsistent, the conversion API/data model conflicts with the attribution model, and some operational controls are still mostly follow-ups rather than integrated design mechanisms.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | The architecture is credible and much sharper than before; capacity and event-contract details still need cleanup. |
| Production realism | 4/5 | DLQ, idempotency, watermarks, and settlement are now present; fraud, privacy, audit, and state sizing need deeper integration. |
| Pedagogical flow | 4/5 | The step order remains strong and the "why now" progression is clear. A few examples still send mixed signals. |
| Dataset/rendering fit | 4/5 | Structured views, links, step references, and probe links check cleanly. Minor stale labels and an unused DLQ edge remain. |
| Overall | 4/5 | Strong interview with a few high-leverage fixes before it feels production-complete for billing analytics. |

## What Works Well

- The prior review's biggest gaps were addressed: capacity is no longer hand-wavy, the API includes typed events, and the data model now includes `credited_conversion` and versioned `metric_rollup` rows.
- The accepted-event boundary is now explicit: the collector should return 202 only after the event is replicated to the log.
- Step 3 introduces event time, watermarks, late-arrival policy, and idempotent OLAP upserts at the right point in the journey.
- Step 4 now distinguishes bounded real-time dedup from global/billing correctness and explains checkpointed state plus idempotent output writes.
- Step 5 is much better: real-time attribution uses recent-click keyed state, while raw-store joins are reserved for batch/backfill.
- Step 6 and Step 7 now give the serving layer a deterministic source/version/settlement model instead of a vague "batch overwrites speed" claim.

## Highest-Impact Issues

### 1. Kafka partition math is internally inconsistent

The capacity section says `~400 MB/s` ingest bandwidth and `~2,000-4,000` Kafka partitions, justified by `~10-20 MB/s effective per partition`. That arithmetic does not work: 400 MB/s divided by 10-20 MB/s implies roughly 20-40 partitions for sustained bandwidth, or about 60-120 partitions at the stated 3M events/sec peak if event size stays near 400 bytes.

The design may still want thousands of partitions for event-rate parallelism, tenant isolation, hot-key spreading, operational headroom, retention/reassignment behavior, or consumer concurrency. But the current note says thousands are needed by the MB/s assumption, which undercuts trust in the rest of the capacity math.

Concrete fix:

- Recompute the partition estimate from separate assumptions: bandwidth per partition, events/sec per partition, peak headroom, replication, and consumer parallelism.
- Explain whether the partition key is salted `campaign_id`, random/event-id, tenant+bucket, or a two-stage repartition, because attribution and aggregation need different locality.
- Add a comparable estimate for multi-day click-state attribution. Seven days of click state can dominate the hot-path state footprint more than the dedup window.

### 2. The conversion event contract conflicts with attribution

The `POST /v1/events` example rejects the conversion event for `missing_required_field: campaign_id`, but the attribution step says a conversion is matched to recent clicks to determine the credited campaign. If conversions must already include `campaign_id`, the purpose of attribution becomes ambiguous. If campaign is derived by joining to a click, then `raw_event.campaign_id` cannot be required for every event type.

There is also a stale sequence label: the ingest API sequence still says `append (partition by adId)`, while the rest of the dataset uses `campaign_id`.

Concrete fix:

- Make event-type required fields explicit. Impressions/clicks should carry campaign/creative/placement; conversions should carry conversion-specific fields plus `user_id`, `session_id`, `click_id`, order id, or another matching key.
- Make `raw_event.campaign_id` nullable for conversions, or call it `source_campaign_hint` if it is optional and not authoritative.
- Change the example rejection to a genuinely invalid conversion field, such as missing `event_id`, invalid `schema_version`, unsupported currency, or no usable attribution identity.
- Update the sequence label from `adId` to the current partitioning strategy.

### 3. Billing-grade risk controls are still mostly outside the main design

The follow-ups now mention invalid traffic, privacy, schema evolution, and billing disputes, which is a good improvement. For ad analytics, these are not only optional interview extensions: they shape accepted events, attribution, raw retention, query access, and settlement.

Concrete fix:

- Add a small invalid-traffic/fraud branch or trap: bot clicks, click spam, suspicious IP/device patterns, and post-settlement invalid-traffic adjustments.
- Turn privacy from a follow-up into at least a design note: consent filtering, pseudonymous identifiers, PII minimization, retention, erasure handling, and access controls on raw events.
- Add an audit/correction model for billed numbers: which metric version produced the invoice, who approved a correction, and how advertisers see deltas.
- Add observability to the final design or a dedicated operations note rather than leaving it only in Step 7 bottlenecks.

### 4. Some examples lag behind the improved correctness model

The descriptions now emphasize idempotent upserts keyed by `(metric_key, window, source, version)`, but a few examples still use older language such as "increment windowed count" and "overwrite rollups." That is understandable shorthand, but it weakens the lesson because the whole point of the update is that blind increments and blind overwrites are unsafe after crashes and replays.

Concrete fix:

- In the dedup sequence, replace "increment windowed count" with an idempotent upsert or emit/update of a window aggregate version.
- In the batch sequence and option copy, use "write batch version" plus "publish settlement marker" rather than "overwrite rollups."
- Include `computed_at` in the query response if the rollup model promises it as the freshness indicator.

## System Design Soundness

The core lambda-style design is sound: collect fast into a durable log, archive immutable raw events, stream provisional metrics, deduplicate retries, attribute conversions with state, recompute accurate closed windows in batch, and serve rollups through a query API. The current version explains the correctness boundary much better than the previous review did.

The main soundness risk is now precision rather than missing architecture. Capacity numbers need to be internally consistent, especially because they justify partitioning, replay windows, and state size. The event model also needs to state which fields are required by event type. Otherwise the design appears to require a conversion to know the campaign before the attribution system determines it.

The source/version/settlement model is a strong addition. Keep pushing it through every example so the candidate learns the concrete mechanism, not just the phrase "batch corrects speed."

## Step-by-Step Pedagogical Review

### Step 1: Naive: Increment a Counter Row Per Event

Still a very effective baseline. The added hot-row example makes the bottleneck concrete. No major change needed.

### Step 2: Durable High-Throughput Ingestion

This step is now much stronger because it defines when an event is accepted and routes invalid/schema-incompatible events to a DLQ. Fix the stale `adId` partitioning label and make the partitioning discussion consistent with the capacity section.

### Step 3: Speed Layer: Real-Time Metrics

The event-time and watermark explanation is well placed and makes later dedup/batch/serving behavior coherent. The remaining improvement is visual: the high-level architecture defines `stream-dlq`, but Step 3 does not show the Stream -> DLQ/correction path even though the text says too-late events are routed there.

### Step 4: Deduplicate for Correct Counts

The updated wording around bounded exactness, checkpoints, and idempotent OLAP writes is good. The flow should stop saying "increment" and should mirror the idempotent upsert model. Add state-size math tied to the dedup window if space allows.

### Step 5: Attribution: Credit Clicks for Conversions

This is now one of the strongest steps. Moving the hot path to click-state storage fixed the previous raw-store lookup problem. The next improvement is to reconcile the API/data model with this step: conversions should provide matching identity, not necessarily a required campaign id.

### Step 6: Batch Layer: Accurate, Reprocessable Metrics

The versioned-row and settlement-marker language is strong. Tighten the sequence copy so it says "write batch version, validate, publish settlement marker" instead of generic overwrite. Consider adding batch runtime and replay isolation numbers from the capacity section.

### Step 7: Serve: Pre-Aggregation and Query

The serving contract is much clearer now: settled windows use batch rows, open windows use speed rows, and responses expose source/settled state. Add the promised `computed_at` field to the sample response and keep query limit/dimension allowlist language.

## Final Design Review

The final design now integrates the steps well. It includes the collector, log, raw store, stream processor, dedup store, attribution service, click-state store, DLQ, batch processor, OLAP store, query API, and dashboard. The previous final-design ambiguity around raw-store attribution and vague overwrites has been largely fixed.

The final design would become production-grade with three refinements:

- Correct the capacity math and add click-state/batch-runtime sizing.
- Align event-type schemas with attribution behavior.
- Promote fraud/privacy/audit/observability from follow-up prompts into explicit design mechanisms.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: durable log, stream processing, event time/watermarks, dedup, attribution, lambda reconciliation, and rollups. This lets a candidate solve one exposed problem at a time.

The best teaching improvement would be to make field contracts as precise as mechanism contracts. The walkthrough is now precise about acceptance, checkpoints, and settlement; it should be equally precise about what an impression, click, and conversion must contain.

## Step-to-Final-Design Coherence

Step-to-final coherence is much improved. Every step contributes a visible final-design component, and the added `ClickState` and `DLQ` nodes make the architecture more honest.

The main coherence gaps are small but concrete:

- `stream-dlq` exists in `highLevelArchitecture.links` but is not shown in the final design or Step 3 view.
- The API sequence says `adId`; the rest of the design says `campaign_id`.
- The query model promises `computed_at`, but the sample response only shows `source` and `settled`.

## Realism Compared With Production Systems

The dataset now captures the broad shape of a production ad analytics system. It accounts for retry duplicates, out-of-order events, bounded dedup, late data, batch correction, and source/versioned serving.

The remaining realism gaps are domain-specific:

- Click-state attribution over a multi-day window needs sizing and retention policy.
- Invalid traffic/fraud can change billed metrics after apparent settlement.
- Privacy and consent affect whether identity can be joined at all.
- Raw-event retention and erasure obligations shape the data lake design.
- Billing disputes need an audit trail and controlled correction workflow.

These can be added as traps, failure drills, final-design notes, or one compact "operations and risk" section without changing the main step order.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Step, option, and final-design `view.nodes` string references resolve to high-level architecture nodes.
- Step, option, and final-design `view.links` string references resolve to high-level architecture links.
- `patterns[].steps`, `satisfies[*].steps[*]`, and step `probeLinks` resolve cleanly.
- Node types are canonical: `cache`, `client`, `database`, `object-storage`, `queue`, `service`, `stream`, and `worker`.
- `stream-dlq` is defined but unused in rendered views. That is not broken, but it is a missed opportunity because Step 3 discusses late-event quarantine.
- No docs rebuild is needed for this `REVIEW.md`-only change.

## Recommended Edits, Prioritized

### P1: Correct the capacity math

Fix the partition estimate and split bandwidth, event-rate, hot-key, peak-headroom, and consumer-parallelism assumptions.

### P1: Align conversion events with attribution

Make event-type required fields explicit, make conversion campaign fields nullable/derived, and update the rejected-event example and stale `adId` sequence label.

### P2: Quantify attribution state and replay runtime

Add back-of-the-envelope sizing for multi-day click-state retention, batch replay duration, and backfill isolation.

### P2: Integrate billing-domain controls

Add invalid-traffic/fraud, privacy/consent/retention, observability, and billing audit/correction as first-class design notes or traps.

### P2: Make examples match versioned correctness

Update sequence labels and option copy to use idempotent upsert, batch version, validation, and settlement-marker language consistently.

### P3: Show the stream quarantine path

Use the existing `stream-dlq` link in the speed or final-design view if late/unparseable stream events are part of the design.

## What Not To Change

- Keep the naive baseline; it teaches the motivation cleanly.
- Keep the speed/batch/lambda structure. The kappa alternative is useful, but lambda is a credible default for billing-grade correction.
- Keep click-state attribution on the hot path and raw-store attribution in batch.
- Keep the source/version/settlement serving model; it is the strongest recent improvement.

## Bottom Line

The recent changes moved this from a good pipeline sketch to a strong analytics interview. The next edit pass should focus on consistency: fix the partition math, align the conversion contract with attribution, and make the billing-risk controls explicit enough that the design feels accountable, not just scalable.
