# Review: Amazon Product Catalog - System Design

Reviewed file: `data/book/product-catalog/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong, compact walkthrough for the core product-catalog pattern:
normalized writes, read-optimized projections, faceted search, denormalized
product views, and a consistency split for volatile stock/price. The sequence
is easy to teach and the default options are mostly the right interview answer.

The current dataset is not yet at the depth of the strongest book cases. It
states several production claims without enough model or workflow support:
fresh price is promised but not drawn as a live dependency, capacity is mostly
qualitative, the seller/update path lacks versioning/idempotency/moderation
details, and projection/rebuild operations are described but not deeply taught.
There are also two narrow renderer-facing view issues where a step uses a
gateway link without including the gateway node.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.0/5 | The CQRS/search/read-model architecture is sound; price, seller, rating/image, and projection invariants need more explicit modeling. |
| Production realism | 3.7/5 | Good high-level trade-offs, but capacity math, price/inventory authority, CDC failure handling, and operational controls are thin. |
| Pedagogical flow | 4.2/5 | The seven-step progression is clear and builds well; it needs deeper drills around projection lag, rebuilds, and purchase-time freshness. |
| Dataset/rendering fit | 4.0/5 | JSON parses and cross-links mostly resolve; two step views omit `LB` while using `lb-*` links, and the price live-read path is not represented. |
| Overall | 4.0/5 | Usable and coherent; one focused expansion pass would make it a polished commerce/catalog chapter. |

## What Works Well

- The core scope is clear: read-heavy browse/search, seller writes, low-latency
  product pages, and special treatment for volatile price and stock.
- Step 1 is a useful baseline. It exposes why a normalized write table is the
  wrong serving shape for search, facets, and product-page rendering.
- The CQRS progression is coherent: split writes from reads, add search/facets,
  add a denormalized read model, then keep derived stores fresh with a stream.
- The options are real trade-offs rather than strawmen. The rejected choices
  are plausible for smaller systems and explain why catalog scale changes the
  decision.
- The final design integrates the main read path, write path, projection path,
  search index, read model, inventory service, and pricing service.
- The wrap-up sections map requirements back to steps cleanly, and the
  interview script is short enough to be usable.

## Highest-Impact Issues

### 1. Fresh price is promised but not modeled or diagrammed as a live read

The requirements, product-detail API description, Step 6, final design, and
`satisfies` section all say price and availability are read live from their
owners at purchase-decision time. Inventory is represented by `InvSvc`,
`InvDB`, and the `detail-inv` link. Pricing has only `PriceSvc` and
`price-stream`; there is no price store, no `CatalogSvc -> PriceSvc` live-read
link in the high-level architecture, and the product-detail API sequence calls
only `InvSvc`.

Why it matters: the dataset teaches "consistency by data type" as the main
senior-level insight, but the rendered diagrams show a concrete live inventory
path and only an event-emission pricing path. Readers can leave thinking price
freshness is solved by projection, which is the opposite of the stated default.

Concrete fix: add a pricing store or explicitly state that the Pricing Service
owns its own external/hidden store. Add a canonical `detail-price` or
`decision-price` link from `CatalogSvc` or the checkout/order boundary to
`PriceSvc`, include it in Step 6 and `finalDesign.view.links`, and update the
product-detail sequence to call both `InvSvc` and `PriceSvc` when the response
claims live price. If live price only happens outside the catalog at checkout,
make that boundary explicit.

### 2. Capacity is too qualitative for the design decisions it justifies

The capacity section says "100s of millions", "reads >> writes", "very
frequent", and "< 200 ms p99", but it never converts that into query QPS,
product-view working set, index size, projection throughput, write burst size,
price/stock update rates, cache hit assumptions, or rebuild duration.

Why it matters: the architecture is justified by scale. Without concrete
orders of magnitude, choices like sharded search, edge caching, stream
buffering, and read-model rebuildability feel asserted rather than derived.

Concrete fix: add approximate numbers, even if rough: daily active shoppers,
search/detail QPS, seller update QPS, peak price/stock event rate, product-view
size, index size, search shard count, cache TTL/hit-rate target, projection lag
SLO, and maximum acceptable full/partial rebuild time. Then tie Step 7 to those
numbers.

### 3. The seller write path lacks production safety details

The API has `PUT /v1/products/{id}` with a simple `{title, attrs}` request and
`{version}` response. The write model has `product_id`, `category_id`, `brand`,
`attributes`, and `version`, but no `seller_id`, ownership/authorization,
idempotency key, optimistic concurrency condition, moderation state, audit log,
or validation workflow for category-specific attributes.

Why it matters: seller updates are one of the stated functional requirements.
At marketplace scale, bad write semantics create overwritten edits, unauthorized
changes, invalid facets, abusive content, and projection churn. These are not
edge cases for a product catalog.

Concrete fix: add seller ownership and write-safety fields: `seller_id` or
owner relation, `status`/moderation state, `updated_at`, `version`, maybe
`attribute_schema_version`, and a write API that uses `If-Match` or an explicit
expected version plus idempotency for create/import operations. Mention
validation of category-specific attributes before they enter search facets.

### 4. Projection and rebuild operations need more failure semantics

Step 5 says the stream is durable and projectors are idempotent, and Step 7 says
derived stores are rebuildable. The data model only has `source_version` on
`product_view`; there is no event ID, outbox/CDC position, projector checkpoint,
dedupe key, lag metric, dead-letter workflow, poison-event behavior, or partial
reindex strategy.

Why it matters: the projection pipeline is the mechanism that keeps two user
visible read stores correct. A production answer should explain how duplicate
events, out-of-order events, projector crashes, bulk imports, and corrupted
index shards are detected and recovered.

Concrete fix: add a deep dive or failure drill for projection mechanics:
transactional outbox/CDC source, event IDs, per-product version ordering,
idempotent upserts, projector checkpoints, DLQ/retry policy, lag SLOs, and
partial rebuild by product/category/shard before full reindex.

### 5. Product-page data is under-modeled for the fields the requirements show

The requirements mention images, rating/reviews summary, categories, brand,
price, availability, facets, and sorting by rating/price. The data model only
has `products`, `product_view`, and `inventory`. Images, review/rating summary,
category hierarchy, price/offers, and search facet normalization are either
buried inside JSON or not represented.

Why it matters: denormalization works only if the reader understands which
source owns each field and which freshness guarantee applies. Hiding all of
that inside `rendered json` makes the read model look simpler than the real
projection problem.

Concrete fix: keep the model compact, but add source ownership rows or notes:
`product_images` or media service, `category` hierarchy, `rating_summary`,
`price/offers`, and `facet_attributes` with normalized values. State which are
projected into `product_view` and/or `SearchIdx`, and which are live at
purchase time.

## System Design Soundness

The main architecture is correct for the stated problem. A normalized product
write model should not serve massive search and product-detail traffic
directly. A search index plus a denormalized read model is the right default,
and a change stream feeding both derived stores is a defensible way to handle
seller edits, category/rating changes, and bulk imports.

The most important soundness gap is the price boundary. The prose says price is
fresh and authoritative, but the graph does not show how. Either the catalog
detail endpoint must synchronously call Pricing Service for display price, or
the catalog should show an approximate/display price while the cart/checkout
system verifies an authoritative price quote. Both are valid, but the dataset
currently mixes them.

Inventory is more concrete than pricing because it has an owner service and
store. It still stops short of purchase semantics: there is no reservation,
hold, or checkout integration. That may be acceptable for a catalog case, but
then the language should say "fresh enough to shop/display" and "verified by
checkout" instead of implying the product catalog itself solves purchase
correctness.

Search and faceting are well scoped. The dataset should add one sentence on
facet normalization and index freshness: category-specific attributes need
controlled schemas, normalized values, and rules for fields that are searchable
versus filterable. Otherwise `attributes json (facetable)` makes the hard part
look automatic.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Query the Normalized Products Table Directly

This is a good baseline. It names the two failures that motivate the rest:
LIKE/facet scans do not meet search latency, and per-request joins do not meet
product-page latency under read-heavy traffic.

The step could be stronger if it included one concrete failure number, such as
an example search QPS or product count that makes SQL faceting untenable.

### Step 2: Split Reads from Writes (CQRS)

This step introduces the central pattern at the right time. The default option
is the right answer, and the read-replica alternative is fairly explained.

The step's current view is still write-path heavy; it does not yet show the
read model or search index even though the text says those stores are derived.
That is acceptable as an incremental reveal, but the caption should make clear
that this step is establishing the source of truth before the read stores are
drawn in later steps.

### Step 3: Search and Faceting

This is one of the strongest steps. It distinguishes product search from plain
keyword search by calling out facet counts, ranking, filters, and result-card
hydration from the read model.

Add more operational depth around index layout: shard key, replicas, hot
queries/categories, refresh interval, and how price/rating facets stay fresh
when those values change often. If price is live-only at purchase, be careful
about using price as a search facet without explaining acceptable staleness.

### Step 4: Denormalized Product Read Model

The step teaches the right latency mechanism: turn multi-source fan-out into a
single render-ready lookup and keep a source version for verification.

The read-model schema is too compressed. It would help to show which fields are
projected content, which are derived summaries, and which are deliberately not
trusted for purchase decisions. The flow calls only inventory live even though
the note says stock and price are volatile.

### Step 5: Keep Read Stores Fresh via Change Streams

This step completes the CQRS story and correctly rejects synchronous dual-write
and periodic full reindex as defaults.

For book-level polish, add a projection mechanics deep dive. The dataset should
teach idempotent event application, per-product version ordering, checkpointing,
lag monitoring, retry/DLQ behavior, and partial rebuild. Those are the real
production details behind "durable stream + projector".

### Step 6: Inventory and Price: Freshness Where It Matters

This is the most important conceptual step. The split between eventually
consistent catalog content and authoritative volatile values is exactly the
right senior interview point.

The diagrams and model need to catch up. Add the live pricing link/store, and
clarify whether the catalog endpoint itself verifies price or whether cart/order
does. Also consider a short trap about over-projecting price because it makes
search/detail fast but breaks purchase trust.

### Step 7: Scaling Reads, Hotspots, and Rebuilds

The closing themes are right: sharding, replication, edge caching, projection
burst buffering, and derived-store rebuilds.

The step is currently too high-level. Add one or two concrete drills: hot
category/search query, viral product detail page, projector lag during a bulk
import, and corrupted index shard. For each, name the expected behavior and the
operational signal that tells the team it is working.

## Final Design Review

The final design is coherent and includes all major components introduced by
the steps. It is a good summary of the intended architecture.

The main defect is the same price-path mismatch: `PriceSvc` appears only through
`price-stream`, while the final description says volatile stock/price are read
live. Add the live price edge or explicitly move price verification out to an
adjacent checkout/order system.

The final design also says reads are edge-cached, but there is no cache/CDN node
in the high-level architecture. Either add an edge cache/read-through cache node
for Step 7/final design or soften the claim to "can be edge-cached".

## Concept Introduction and Learning Flow

The concepts are introduced in a clean order: CQRS, faceted search,
denormalized read model, projection, consistency by data type, and bounded
service ownership. That is the right sequence for this problem.

The missing teaching pieces are mostly operational concepts: transactional
outbox or CDC, projector idempotency, projection lag SLO, partial reindex,
facet normalization, and price quote/verification boundaries. These should be
introduced only where needed rather than as a separate theory block.

## Step-to-Final-Design Coherence

The final design mostly reflects the steps: search/read model from Steps 3-4,
change stream/indexer from Step 5, inventory/pricing services from Step 6, and
sharded/replicated/cached reads from Step 7.

The coherence gaps are narrow but important:

- Step 6 says live pricing; final design does not show a live price edge.
- Step 7 says edge caching; final design does not show an edge cache/CDN node.
- Step 4 and Step 6 mention live volatile values; the API sequence only calls
  inventory.
- The write path says seller updates, but final design has no seller/admin
  client distinction, auth, moderation, or write conflict handling.

## Realism Compared With Production Systems

The dataset is realistic at the architecture-pattern level. It captures the
big idea used by large e-commerce catalogs: separate product authoring from
browse serving, use a dedicated search system, denormalize product pages, and
treat fast-changing commercial data differently from descriptive content.

It is less realistic at the operational and domain-boundary level. A production
catalog has marketplace ownership, offer/price authority, media, category
taxonomy, facet schema management, review/rating summaries, moderation, bulk
imports, abuse controls, and explicit checkout handoff. The dataset does not
need to cover all of these, but it should name the ones intentionally out of
scope and model the ones it relies on for correctness.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- `satisfies[*].steps[*]` and `patterns[*].steps[*]` resolve to existing step
  IDs.
- Step/option/final-design string link IDs resolve to
  `highLevelArchitecture.links`.
- Sequence message participants resolve within their sequence, and sequence
  participants map to canonical high-level node IDs.
- Main Step 3 uses `lb-search` but `view.nodes` omits `LB`; Main Step 4 uses
  `lb-detail` but `view.nodes` omits `LB`. Add `LB` to those views or replace
  the links with local `Client -> SearchSvc` / `Client -> CatalogSvc` links.
- Canonical node types used by the high-level architecture are supported:
  `cache`, `client`, `database`, `edge`, `index`, `service`, `stream`, and
  `worker`.
- `ReadModel` is typed as `cache`. That renders, but semantically it is a
  persistent derived read store. Consider whether `database` better matches the
  teaching intent, or keep `cache` and explicitly say it is rebuildable derived
  state rather than a simple volatile cache.

## Recommended Edits, Prioritized

### P1: Fix the live price path

Add pricing storage/ownership, a live price link, and a product-detail or
purchase-decision sequence that calls Pricing Service when the text promises
fresh price. Clarify whether price verification belongs to catalog or checkout.

### P1: Add concrete capacity and lag numbers

Turn qualitative capacity bullets into rough operating estimates and use them
to justify shard counts, cache strategy, projection throughput, and rebuild
strategy.

### P1: Expand projection failure handling

Add a Step 5 deep dive or failure drills for event IDs, idempotent upserts,
checkpoints, lag SLOs, DLQ behavior, bulk imports, and partial reindex.

### P2: Strengthen the seller write model

Add seller ownership, expected-version writes, idempotent create/import, status
or moderation fields, audit metadata, and category-specific attribute
validation.

### P2: Make product-page source ownership visible

Add compact model notes for media/images, category hierarchy, rating summary,
price/offers, and facet attributes. Do not bury every important source inside
`rendered json`.

### P2: Fix the two main view endpoint omissions

Add `LB` to the Step 3 and Step 4 main `view.nodes`, or switch those views to
local client-service links.

### P3: Add Step 7 operational drills

Add drills for viral product reads, hot category/search queries, projector lag
during import, and corrupted index shards. Keep them concise and tied to the
existing architecture.

## What Not To Change

- Keep the seven-step CQRS progression. It is the dataset's main strength.
- Keep faceted search as a dedicated step; it is the e-commerce-specific
  teaching point.
- Keep the denormalized read model separate from the search index. The
  distinction between candidate retrieval and result hydration is useful.
- Keep consistency-by-data-type as the senior-level insight. Fix the diagrams
  and model around it rather than replacing it.
- Do not turn this into a full checkout/order-management case. Name the
  boundary and handoff instead.

## Bottom Line

This is a good product-catalog interview dataset with the right core answer and
a clear teaching arc. To make it book-polished, focus on concrete capacity,
explicit price/purchase boundaries, projection operations, seller-write safety,
and the two small view fixes. The architecture does not need a rewrite; it needs
the production details to support the claims it already makes.
