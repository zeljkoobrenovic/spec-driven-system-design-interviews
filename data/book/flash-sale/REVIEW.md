# Review: Flash Sale - System Design

Reviewed file: `data/book/flash-sale/interview.json`
Review date: 2026-06-08

## Executive Summary

This is now a strong, production-credible flash-sale walkthrough. Recent changes addressed the earlier major gaps: capacity math is concrete, admission-token semantics are explicit, reservation/payment state is modeled, order status and payment callback APIs exist, counter failover is discussed, failure drills were added, and `technologyChoices` is populated.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | The core design is defensible: CDN/edge offload, waiting-room admission, token-gated atomic reservation, async orders, ledger reconciliation, and fail-closed counter recovery. |
| Production realism | 4.3/5 | Good treatment of idempotency, payment ambiguity, duplicate queue delivery, and Redis failover. Remaining gaps are mostly around waiting-room durability/abuse policy and operational runbooks. |
| Pedagogical flow | 4.6/5 | The steps expose one problem at a time and the decision prompts are strong. The walkthrough is compact without skipping the central mechanisms. |
| Dataset/rendering fit | 4.6/5 | JSON parses; structured views/sequences are used correctly; node, link, group, participant, pattern, satisfy, and technology step references resolve. |
| Book completeness | 4.2/5 | Includes patterns, traps, drills, scripts, level variants, probe links, and technology choices. It still lacks optional AI visuals/comic and per-requirement illustrations. |

## What Works Well

- The capacity section now turns the scenario into usable numbers: 10M arrivals, 10K units, admitted rate, buy attempts/sec, queue/payment throughput, and hold-expiry volume.
- The admission token is specified as identity-bound, single-use, expiring, and tied to `sale_id`, `user_id`, `admission_id`, and `max_qty`.
- The data model now supports the claims in the design: `admissions`, `reservations`, `payment_attempts`, `orders`, and `stock_ledger_events` cover idempotency, holds, payment ambiguity, and counter rebuilds.
- The `reserve`, `async`, and `consistency` steps are much sharper than before: guarded decrement-if-positive, duplicate queue delivery, PSP timeout ambiguity, fail-closed Redis recovery, epoch fencing, and idempotent reaping are all present.
- `technologyChoices` is useful and domain-specific, comparing edge/waiting-room, token, counter, queue, order-store, and payment options across self-hosted and cloud stacks.
- The final design now lines up with the requirements, APIs, data model, failure drills, and satisfies mapping.

## Highest-Impact Issues

### 1. Waiting-room durability and fairness policy need one more level of precision

The dataset now gives a clear token contract, but the waiting room itself is still described mostly as "durable ordered queue at the edge." At 10M arrivals in 1-2 seconds, that state is the first hard production problem. The default FIFO design needs to explain how queue entries are deduped, persisted, replicated, and recovered without losing place or admitting duplicates.

Concrete fix: add a deep dive or failure drill under Step 4 covering waiting-room state. Include `queue_entry_id`, `(sale_id, user_id)` uniqueness, shard/partition strategy, replay behavior after edge-region failure, and whether FIFO is global, per-region, or windowed. If global FIFO is too costly, say so and frame FIFO as "best effort within an arrival window."

### 2. Abuse prevention is named but not operationalized

The text mentions account/session identity, bot challenge, and per-user/per-household limits. That is directionally right, but a flash-sale case lives or dies on the exact abuse boundary: account farms, device reuse, shared IPs, captcha bypass, token sharing, and multiple browser sessions.

Concrete fix: add one short anti-abuse drill. Example: "A reseller creates 50K fresh accounts before T0." Expected behavior could combine pre-sale account eligibility, device/risk scoring, velocity checks, household/payment-method limits, and manual override/appeal. Keep it scoped so it teaches trade-offs instead of becoming a fraud platform.

### 3. Admission-rate control is quantified in capacity but not fully connected to runtime feedback

The capacity section says to admit about `stock / completion_rate` users, metered over 1-5 minutes. That is useful, but the runtime control loop is implicit. In production, the admission service needs to react to live reservations, payment completion, expired holds, counter value, queue backlog, and worker/payment health.

Concrete fix: add a sentence in Step 3 or Step 4: admission is a feedback controller, not a fixed constant. It should slow or pause when the counter is near zero, payment/order workers are unhealthy, or the counter epoch is uncertain; it can admit another tranche when holds expire or payment completion is lower than expected.

### 4. Payment UX is improved but the checkout boundary is still ambiguous

The API now exposes reservation polling and an internal payment callback, which fixes the biggest prior gap. The remaining ambiguity is how payment is initiated: `/buy` has only `{ token, idempotencyKey }`, while the async worker "charges the buyer." That implies a stored payment method or pre-authorized checkout context, but the dataset does not say which.

Concrete fix: either add a `paymentMethodId` / `checkoutSessionId` to `/buy`, or explicitly state that the product assumes a logged-in buyer with a stored default payment method and PSP customer reference. The `payment_attempts` entity should then carry that reference or a checkout session.

### 5. Technology choices are strong, but fallback icons remain for several chips

This is not a design correctness issue, but it is visible in the rendered book page. Current fallback `tech.png` chips include Apigee, Azure CDN, PASETO, Keycloak, Azure Cache for Redis, Azure SQL, direct PSP API, and AWS Payment Cryptography.

Concrete fix: add mappings in `_media/index.yaml` for the common missing terms where real icons exist, then rerun the tech icon assignment script. For generic terms like "Direct PSP API (Stripe/Adyen/Braintree)", the fallback may be acceptable.

## System Design Soundness

The system design is now coherent end to end. It correctly treats a flash sale as a rejection and contention problem rather than a normal e-commerce throughput problem. Reads are offloaded to the CDN, most entrants are held or shed at the edge, the purchase core only sees admitted traffic, and the scarce-inventory invariant is reduced to one guarded atomic operation.

The best part is the explicit correctness boundary around the inventory counter. The design no longer hand-waves Redis failure: it identifies the durable ledger as authority, describes epoch fencing, and says the buy path fails closed when counter authority is uncertain. That is the right trade-off for scarce stock.

The data model now backs the architecture's promises. `admissions` supports token issuance and per-user limits; `reservations` supports holds and idempotent retries; `payment_attempts` supports PSP ambiguity; `orders` is separated from held reservations; `stock_ledger_events` supports rebuild and reconciliation.

The main remaining design question is not "does this prevent oversell?" but "how does the waiting room survive the same 10M-user spike?" The answer can be shorter than the counter deep dive, but it should exist because Step 4 makes the waiting room the primary fairness mechanism.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Everyone Hits Buy, Decrement Stock in the DB

Strong opening. It explains why both separate read/check/decrement and DB-row locking fail under the spike. The diagram was fixed to use a local "buy request" label instead of leaking future token semantics.

### Step 2: Offload Reads to the Edge

This is the right first move. The step cleanly separates page/availability reads from admission and buy attempts. It could mention cache invalidation on sold-out state, but Step 7 already covers stale CDN availability enough for this level.

### Step 3: Admission Control at the Edge

Good survival framing: most traffic cannot succeed and should fail cheaply. The step would be stronger if it tied the capacity numbers directly to an admission-control loop: admit a tranche, observe reservation/payment/expiry outcomes, then adjust.

### Step 4: Fairness: Virtual Waiting Room

This is now a strong section. The default FIFO, lottery, and token-bucket options compare real trade-offs. The token claims and single-use behavior are clear. Add one production detail on queue-state durability and recovery so "durable ordered queue" is not a black box.

### Step 5: Oversell-Proof Reservation

Very strong. The guarded decrement-if-positive primitive is precise, and the step correctly warns against `DECR` followed by compensating `INCR`. Idempotency is introduced exactly where it matters.

One small inconsistency: the pre-minted reservation-token option says "Mint exactly 100" even the capacity scenario uses 10K units and the decision prompt says 100 units. This may be intentional for the prompt example, but the option would read cleaner as "one per unit" or "exactly N tokens."

### Step 6: Async Order Creation and Payment

Much improved. Duplicate queue delivery and ambiguous payment timeout drills are the right production failures. The next refinement is clarifying payment initiation: stored payment method, checkout session, or separate pay-now flow.

### Step 7: Consistency, Reconciliation, and Degradation

This is now one of the strongest sections. It states invariants, fail-closed behavior, epoch fencing, rebuild from ledger, idempotent reaping, and CDN staleness. The only thing to avoid in future edits is expanding it into a full distributed-consensus lesson; it is currently detailed enough for a system design interview.

## Final Design Review

The final design integrates the introduced components cleanly: `CDN`, `Edge`, `WaitRoom`, `Token`, `BuySvc`, `Inventory`, `OrderQ`, `OrderSvc`, `OrderDB`, and `PaySvc`. It maps well to the APIs and data model.

The strongest improvement over the previous review is that final-design claims are now backed by durable state and API surfaces. Reservation holds, token consumption, payment status, duplicate payment handling, and counter recovery are no longer just prose.

The remaining final-design gap is operational: what dashboards and kill switches does the operator use during the drop? A compact mention of admission pause, sold-out override, counter rebuild status, queue depth, payment error rate, and token issuance rate would make the design feel fully operable.

## Concept Introduction and Learning Flow

The concept staging is effective:

- Static edge offload before admission.
- Load shedding before fairness.
- Waiting-room token before reservation.
- Atomic decrement and idempotency before async order work.
- Hold windows before reconciliation.
- Fail-closed behavior after counter/ledger drift is introduced.

This is a good "just in time" teaching flow. The concepts are not dumped up front, and the `recap.newRisk` fields consistently motivate the next step.

## Step-to-Final-Design Coherence

The coherence is strong. Every major final-design component is introduced by a step, and the `satisfies` mapping points to relevant steps. The strongest through-line is: DB contention fails -> edge absorbs reads -> admission caps the core -> waiting room grants fair tokens -> atomic counter prevents oversell -> async queue handles slow work -> reconciliation preserves correctness under failure.

The only weak transition is between "admitted to buy" and "payment can be charged." The current design assumes a payment credential or checkout context exists. Make that assumption explicit so the async payment worker is not magically able to charge the buyer.

## Realism Compared With Production Systems

The dataset now covers most production issues expected in a strong interview answer:

- identity-bound, expiring, single-use tokens
- per-user purchase cap via admission and reservation uniqueness
- idempotent buy retries
- duplicate queue delivery
- PSP idempotency and webhook ambiguity
- hold expiry and idempotent reaping
- counter/ledger reconciliation
- Redis failover and fail-closed behavior
- CDN sold-out staleness
- concrete cloud/self-hosted technology choices

The next realism upgrades are around operations and abuse: pre-sale account eligibility, account-farm handling, regional waiting-room recovery, live admission throttles, dashboards, and manual sale controls.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Source `data/book/flash-sale/interview.json` and built `docs/book/data/flash-sale/interview.json` are byte-identical.
- Step, option, and final-design string `view.nodes` references resolve to high-level architecture nodes.
- Step, option, and final-design string `view.links` references resolve to high-level architecture links.
- High-level architecture link endpoints resolve to known nodes.
- Sequence participants in APIs and flows resolve to canonical node IDs.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and `technologyChoices[*].steps[*]` references resolve to real step IDs.
- Architecture steps use structured `view` objects and flows use structured `sequence` objects. Raw Mermaid remains only in top-level `requirementsDiagram` and `capacityDiagram`, which matches repo conventions.
- Optional generated visual fields are absent: `aiVisuals`, per-step `aiVisual`, per-requirement `aiVisual`, and `explainerComic`. This is valid, but this case would benefit from an AI visual or comic because the waiting-room/admission flow is easy to explain visually.
- Several technology chips still use the fallback `assets/tech-icons/tech.png`, listed above.

## Recommended Edits, Prioritized

### P1: Add waiting-room state/recovery detail

Add a compact Step 4 deep dive or failure drill for durable queue entries, dedupe, edge-region failure, and whether FIFO is global or windowed.

### P1: Clarify the payment initiation contract

Specify whether `/buy` carries a `paymentMethodId` / `checkoutSessionId`, or whether the system assumes a logged-in buyer with a stored PSP customer/payment reference.

### P2: Connect admission rate to runtime feedback

Explain how the admission service adjusts based on remaining counter value, reservation completion, expiry rate, queue backlog, worker health, payment health, and counter epoch status.

### P2: Add one anti-abuse failure drill

Use an account-farm or token-sharing scenario to make the bot/per-user-limit story concrete.

### P2: Add operator controls and observability

Mention sale dashboard signals and controls: admission pause, sold-out override, token issuance rate, reservation success rate, queue depth, payment failures, hold-expiry rate, counter epoch/rebuild status, and reconciliation drift.

### P3: Normalize the pre-minted-token example

Replace "Mint exactly 100" with "mint one per unit" unless the option is intentionally tied to the 100-unit decision-prompt example.

### P3: Improve fallback technology icons

Map common fallback terms in `_media/index.yaml` and rerun tech icon assignment.

### P3: Consider generated visuals

Add an explainer comic or AI visual for the admission/waiting-room/reservation path if the book page needs a more visual teaching surface.

## What Not To Change

- Keep the current step order. It is the main pedagogical strength.
- Keep the guarded atomic counter as the default reservation answer.
- Keep the waiting-room alternatives; FIFO, lottery, and token-bucket admission teach real product trade-offs.
- Keep the final design compact. The current dataset is focused and interview-friendly.
- Keep fail-closed behavior explicit. It is the key senior-level correctness principle for scarce inventory.

## Bottom Line

This dataset has moved from a good conceptual flash-sale answer to a strong book-quality walkthrough. The remaining work is not architectural overhaul; it is production sharpening around waiting-room durability, abuse handling, payment initiation, operator controls, and a few renderer/polish items.
