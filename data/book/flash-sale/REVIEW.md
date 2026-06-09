# Review: Flash Sale - System Design

Reviewed file: `data/book/flash-sale/interview.json`
Review date: 2026-06-08

## Executive Summary

This is now a strong, production-credible flash-sale walkthrough. Recent changes addressed the earlier major gaps: capacity math is concrete, admission-token semantics are explicit, reservation/payment state is modeled, order status and payment callback APIs exist, counter failover is discussed, failure drills were added, and `technologyChoices` is populated.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | The core design is defensible: CDN/edge offload, waiting-room admission, token-gated atomic reservation, async orders, ledger reconciliation, and fail-closed counter recovery. |
| Production realism | 4.6/5 | Good treatment of idempotency, payment ambiguity, duplicate queue delivery, Redis failover, waiting-room recovery, abuse drills, admission feedback, and operator controls. |
| Pedagogical flow | 4.6/5 | The steps expose one problem at a time and the decision prompts are strong. The walkthrough is compact without skipping the central mechanisms. |
| Dataset/rendering fit | 4.6/5 | JSON parses; structured views/sequences are used correctly; node, link, group, participant, pattern, satisfy, and technology step references resolve. |
| Book completeness | 4.4/5 | Includes patterns, traps, drills, scripts, level variants, probe links, and technology choices. It still lacks optional AI visuals/comic and per-requirement illustrations. |

## What Works Well

- The capacity section now turns the scenario into usable numbers: 10M arrivals, 10K units, admitted rate, buy attempts/sec, queue/payment throughput, and hold-expiry volume.
- The admission token is specified as identity-bound, single-use, expiring, and tied to `sale_id`, `user_id`, `admission_id`, and `max_qty`.
- The data model now supports the claims in the design: `admissions`, `reservations`, `payment_attempts`, `orders`, and `stock_ledger_events` cover idempotency, holds, payment ambiguity, and counter rebuilds.
- The `reserve`, `async`, and `consistency` steps are much sharper than before: guarded decrement-if-positive, duplicate queue delivery, PSP timeout ambiguity, fail-closed Redis recovery, epoch fencing, idempotent reaping, and operator kill switches are all present.
- Step 4 now explains durable waiting-room entries, shard/windowed FIFO, replay after edge-region failure, account-farm abuse, token replay, and why managed waiting rooms are attractive.
- `technologyChoices` is useful and domain-specific, comparing 10 concerns across edge/waiting-room, anti-abuse, token, counter, queue, order-store, payment, workflow, and observability choices.
- The final design now lines up with the requirements, APIs, data model, failure drills, and satisfies mapping.

## Highest-Impact Issues

### 1. Optional generated visuals are still absent

This is not a schema or correctness problem, but this case would teach well with generated visuals: the waiting-room/admission path, the reservation hold window, and the counter-vs-ledger recovery loop are visual concepts.

Concrete fix: add an explainer comic or AI visual assets when the book page needs a more visual teaching surface.

### 2. Technology choices are strong, but a few fallback icons remain

This is not a design correctness issue, but it is visible in the rendered book page. Current fallback `tech.png` chips are PASETO, Direct PSP API (Stripe/Adyen/Braintree), and AWS Payment Cryptography.

Concrete fix: add mappings in `_media/index.yaml` for PASETO and AWS Payment Cryptography if suitable icons are added; the generic "Direct PSP API (Stripe/Adyen/Braintree)" fallback is acceptable.

## System Design Soundness

The system design is now coherent end to end. It correctly treats a flash sale as a rejection and contention problem rather than a normal e-commerce throughput problem. Reads are offloaded to the CDN, most entrants are held or shed at the edge, the purchase core only sees admitted traffic, and the scarce-inventory invariant is reduced to one guarded atomic operation.

The best part is the explicit correctness boundary around the inventory counter. The design no longer hand-waves Redis failure: it identifies the durable ledger as authority, describes epoch fencing, and says the buy path fails closed when counter authority is uncertain. That is the right trade-off for scarce stock.

The data model now backs the architecture's promises. `admissions` supports token issuance and per-user limits; `reservations` supports holds and idempotent retries; `payment_attempts` supports PSP ambiguity; `orders` is separated from held reservations; `stock_ledger_events` supports rebuild and reconciliation.

The main remaining design question is product-specific rather than architectural: how strict should the abuse controls be before they reject too many legitimate buyers? The dataset now has the right hooks for that conversation without turning the interview into a fraud platform.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Everyone Hits Buy, Decrement Stock in the DB

Strong opening. It explains why both separate read/check/decrement and DB-row locking fail under the spike. The diagram was fixed to use a local "buy request" label instead of leaking future token semantics.

### Step 2: Offload Reads to the Edge

This is the right first move. The step cleanly separates page/availability reads from admission and buy attempts. It could mention cache invalidation on sold-out state, but Step 7 already covers stale CDN availability enough for this level.

### Step 3: Admission Control at the Edge

Good survival framing: most traffic cannot succeed and should fail cheaply. The step now ties the capacity numbers to an admission-control loop: admit a tranche, observe reservation/payment/expiry outcomes, then adjust.

### Step 4: Fairness: Virtual Waiting Room

This is now a strong section. The default FIFO, lottery, and token-bucket options compare real trade-offs. The token claims and single-use behavior are clear, and the durable waiting-room deep dive explains queue entries, dedupe, sharding, recovery, and best-effort FIFO scope.

### Step 5: Oversell-Proof Reservation

Very strong. The guarded decrement-if-positive primitive is precise, and the step correctly warns against `DECR` followed by compensating `INCR`. Idempotency is introduced exactly where it matters.

### Step 6: Async Order Creation and Payment

Much improved. Duplicate queue delivery and ambiguous payment timeout drills are the right production failures. The payment initiation boundary is now explicit: `/buy` carries a stored `paymentMethodId`, and the async worker charges the buyer's stored PSP customer/payment reference.

### Step 7: Consistency, Reconciliation, and Degradation

This is now one of the strongest sections. It states invariants, fail-closed behavior, epoch fencing, rebuild from ledger, idempotent reaping, and CDN staleness. The only thing to avoid in future edits is expanding it into a full distributed-consensus lesson; it is currently detailed enough for a system design interview.

## Final Design Review

The final design integrates the introduced components cleanly: `CDN`, `Edge`, `WaitRoom`, `Token`, `BuySvc`, `Inventory`, `OrderQ`, `OrderSvc`, `OrderDB`, and `PaySvc`. It maps well to the APIs and data model.

The strongest improvement over the previous review is that final-design claims are now backed by durable state and API surfaces. Reservation holds, token consumption, payment status, duplicate payment handling, and counter recovery are no longer just prose.

The final design is now operationally grounded: it names the live console signals and kill switches an operator needs during the drop, including admission pause, forced sold-out, counter rebuild, queue depth, payment failures, hold expiry, reconciliation drift, and token issuance rate.

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

The transition between "admitted to buy" and "payment can be charged" is now explicit enough for the scope: the buyer is logged in, chooses/confirms a stored payment method before purchase, and `/buy` passes a `paymentMethodId` reference into the reservation.

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
- durable waiting-room recovery and anti-abuse drills
- live admission throttles, dashboards, and manual sale controls
- concrete cloud/self-hosted technology choices

The next realism upgrades are optional: generated visuals for the sale journey and deeper product-policy detail for false-positive handling.

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
- Three technology chips still use the fallback `assets/tech-icons/tech.png`, listed above.

## Recommended Edits, Prioritized

### P3: Improve fallback technology icons

Map PASETO and AWS Payment Cryptography in `_media/index.yaml` if suitable icons are added, then rerun tech icon assignment. Keep the generic direct-PSP fallback unless a neutral PSP icon is introduced.

### P3: Consider generated visuals

Add an explainer comic or AI visual for the admission/waiting-room/reservation path if the book page needs a more visual teaching surface.

## What Not To Change

- Keep the current step order. It is the main pedagogical strength.
- Keep the guarded atomic counter as the default reservation answer.
- Keep the waiting-room alternatives; FIFO, lottery, and token-bucket admission teach real product trade-offs.
- Keep the final design compact. The current dataset is focused and interview-friendly.
- Keep fail-closed behavior explicit. It is the key senior-level correctness principle for scarce inventory.

## Bottom Line

This dataset has moved from a good conceptual flash-sale answer to a strong book-quality walkthrough. The remaining work is not architectural overhaul; it is renderer/polish work: optional visuals and a few fallback technology icons.
