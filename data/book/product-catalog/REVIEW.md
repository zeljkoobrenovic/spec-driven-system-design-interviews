# Review: Amazon Product Catalog - System Design

Reviewed file: `data/book/product-catalog/interview.json`
Review date: 2026-06-09

## Executive Summary

This review reflects the current `interview.json`, which is materially stronger
than the prior review described. The recent dataset now includes concrete
capacity numbers, a pricing store and live price read path, an edge/CDN cache,
seller write safety fields, category/facet schema modeling, projection
checkpointing, a projection-mechanics deep dive, and explicit bottleneck and
failure drills.

The result is a strong book-ready product-catalog walkthrough. The core answer
is coherent: normalized write model, projected search index, denormalized
product read model, live reads for volatile inventory/price, and rebuildable
derived stores. Remaining gaps are no longer foundational architecture breaks;
they are precision gaps around how stale price participates in search
filtering/sorting, where the purchase/checkout boundary starts, how multi-seller
offers and buy-box prices are scoped, and one small wrap-up mapping mismatch.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | The CQRS/search/read-model design is sound and now has concrete scale assumptions; price/search semantics and offer modeling need one more clarification pass. |
| Production realism | 4.4/5 | Projection, seller writes, live stock/price, and recovery are realistic; purchase quote semantics and multi-seller offers are still mostly named rather than modeled. |
| Pedagogical flow | 4.6/5 | The seven-step progression is clear, motivated, and now has useful drills/deep dives. |
| Dataset/rendering fit | 4.6/5 | JSON parses, links and sequences resolve, and old LB/link issues are fixed; `satisfies.nonFunctional` misses one requirement mapping. |
| Overall | 4.5/5 | A polished and credible catalog case with a few targeted refinements left. |

## What Works Well

- The capacity section now gives useful orders of magnitude: 300M products,
  100M DAU, 500k peak search QPS, 1M peak detail QPS, 50-100k/sec peak
  price/stock events, p99 < 5 s projection lag, and rebuild expectations.
- The CQRS arc is clean: Step 1 exposes the normalized-table failure, Step 2
  creates source-of-truth separation, Step 3 adds search/facets, Step 4 adds
  the denormalized read model, and Step 5 explains projection.
- The data model now supports the story. It includes seller ownership,
  optimistic-concurrency versioning, moderation status, category facet schema,
  rating summary, price/offers, inventory, and projection checkpoints.
- The prior live-price mismatch is fixed. `PriceSvc`, `PriceDB`, `detail-price`,
  the product-detail API sequence, Step 6, and final design now all align.
- Projection operations are no longer hand-wavy. The deep dive covers outbox/CDC,
  event IDs, per-product ordering, idempotent upserts, checkpoints, lag alarms,
  DLQ handling, replay, partial reindex, and full reproject fallback.
- Step 7 now teaches operations, not just scale words. Viral product reads, hot
  search/category queries, projection floods, corrupted shards, lag breaches,
  and poison events all have expected behavior and mitigations.
- The structured diagrams fit the renderer conventions. The previously noted
  Step 3/Step 4 `LB` omissions are fixed.

## Highest-Impact Issues

### 1. Price filtering and sorting need explicit staleness semantics

The requirements and API include price facets/filtering/sorting, while Step 6
correctly says authoritative price is read live from Pricing Service and not
trusted from the projected view. The dataset now includes a trap that says price
facets should be bucketed with explicit acceptable staleness, but that rule is
not yet visible in the API, data model, search step, or requirement mapping.

Why it matters: at 50-100k/sec peak price/stock events, indexing every price
change as a precise search/sort field can churn the index and still serve stale
results. But if price in search is only approximate, the candidate must explain
what the shopper sees when a filtered/sorted result is re-priced by the live
Pricing Service on detail/add-to-cart.

Concrete fix: make the search semantics explicit. Add fields such as
`indexed_price_bucket`, `display_price`, `price_last_projected_at`, or
`winning_offer_snapshot` to the search/read model discussion; state that price
filters/sorts operate on a projected or bucketed snapshot; and say the product
detail/cart path refreshes the top result's current price from Pricing Service.

### 2. The purchase boundary is named, but quote/reservation semantics are thin

Step 6 and `satisfies` now say checkout re-verifies an authoritative price
quote, and this is the right boundary for a catalog case. However, there is no
small explanation of what "price quote" means: quote TTL, quote ID, failed quote
refresh, inventory reservation/hold handoff, or which adjacent service owns the
final purchase decision.

Why it matters: the dataset says price and availability are trustworthy at the
purchase decision. Without a precise boundary, readers can blur "catalog detail
page is fresh" with "checkout correctness is solved by catalog."

Concrete fix: keep checkout out of scope, but add a compact boundary note in
Step 6 or final design: catalog/detail can refresh live display values; cart or
checkout requests an authoritative price quote and inventory reservation/hold;
the quote has a TTL and is revalidated before order placement.

### 3. Multi-seller offers and buy-box behavior are under-scoped

The data model now has `price / offers` with `seller_id`, and follow-ups ask
about many sellers and buy-box behavior. That is good. The main walkthrough,
however, still mostly talks as if each product has one current price.

Why it matters: for an Amazon-style catalog, product identity, seller offers,
display price, price sorting, availability, and buy-box selection are tightly
connected. Treating price as a single product field can mislead candidates when
they later discuss marketplace offers.

Concrete fix: either explicitly scope the default design to "one winning offer
per product is projected/displayed" or add a short offer summary model:
`offer_id`, `seller_id`, `condition`, `fulfillment_channel`, `price`,
`availability`, and `is_buy_box_winner`. Then tie search result price to the
winning-offer snapshot and live checkout to the selected offer.

### 4. `satisfies.nonFunctional` misses one stated non-functional requirement

`requirements.nonFunctional` has five bullets, but `satisfies.nonFunctional`
has four entries. The omitted one is the read-heavy nature of browse/search
traffic, which is central to the case even though it is indirectly covered by
low latency and scale.

Concrete fix: add a `satisfies.nonFunctional` item such as "Extremely
read-heavy browse/search" mapped to `cqrs`, `readmodel`, `search`, and `scale`.

## System Design Soundness

The current architecture is sound for a large e-commerce product catalog. The
write path is normalized and owner-controlled, while browse/search reads use
two derived serving shapes: a search/facet index for discovery and a
denormalized read model for result-card and detail hydration. A durable change
stream and projector complete the CQRS story.

The capacity math now supports the design choices instead of merely asserting
them. The read:write ratio, search/detail QPS, price/stock event rate, cache hit
target, lag SLO, and rebuild bounds explain why one normalized database cannot
serve the whole workload.

Inventory and pricing ownership is now much better modeled. `InvSvc`/`InvDB`
and `PriceSvc`/`PriceDB` own volatile data, emit changes, and are read live
when the product page needs trustworthy values. The remaining design precision
is not "add Pricing Service"; that is already done. The precision needed is
"what does price mean inside search and result ordering if authoritative price
lives elsewhere?"

The write API and data model are credible: seller ownership, `If-Match`,
idempotency key, moderation status, category-scoped attributes, schema version,
and per-product version are the right controls. A future pass could add audit
log and bulk-import job IDs, but the dataset already teaches the important
write-safety concepts.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Query the Normalized Products Table Directly

This is a strong baseline. It now uses concrete scale numbers to make the
failure visible: SQL-like search, facet aggregation, and per-request joins do
not survive hundreds of millions of products and heavy read traffic.

### Step 2: Split Reads from Writes (CQRS)

This step introduces the central pattern at the right moment. The options are
well framed: derived stores are the right default, while read replicas/caching
are plausible but insufficient because they do not change the read shape.

### Step 3: Search and Faceting

This is the e-commerce-specific teaching step and it mostly works well. It
names inverted indexing, facet counts, ranking, shard/replica needs, and result
hydration from the read model.

The main improvement is price semantics. If search supports `maxPrice` and sort
by price, the step should state whether that price is a projected snapshot, a
bucketed range, or refreshed for the top N results. This is especially important
because Step 6 later says price is authoritative only when read live.

### Step 4: Denormalized Product Read Model

This step is now coherent. It teaches the single-lookup product page and includes
a flow that gets content from the read model while reading inventory and price
live. The `product_view` model also clearly labels display price and stock badge
as non-authoritative.

Consider adding one sentence on review/rating and media ownership: those are
projected content summaries, not data owned by Catalog Service.

### Step 5: Keep Read Stores Fresh via Change Streams

This is substantially improved. The projection mechanics deep dive is concrete
and production-realistic: transactional outbox/CDC, event IDs, version guards,
partition ordering, checkpoints, lag alarms, DLQ, partial reindex, and replay.

One small clarity point: the high-level diagram shows catalog, price, and
inventory events in the same `ChangeStream`. That is fine for a conceptual event
bus, but the text should say whether this is one physical stream or a shared
eventing abstraction with owner-specific topics.

### Step 6: Inventory and Price: Freshness Where It Matters

This is the key senior-level step and the recent changes fixed its largest
problem. The live price path is now present in prose, API sequence, links,
nodes, and final design.

The remaining improvement is boundary precision. Say exactly which value is
fresh on the catalog detail page, which value is only a display snapshot in
search/read model, and which adjacent cart/checkout service gets the final
quote/reservation.

### Step 7: Scaling Reads, Hotspots, and Rebuilds

This is now much stronger. The bottlenecks and failure drills make the derived
read stores operationally believable. Viral product reads, hot queries, bulk
imports, corrupted shards, lag breaches, and poison events are the right drills.

Add one optional drill for CDN/query-cache invalidation or stale cached product
content after moderation suppression, since the design now includes an
`EdgeCache`.

## Final Design Review

The final design now integrates the steps well. It contains the client/gateway,
edge cache, catalog service/store, read model, search service/index, change
stream, projector, inventory service/store, and pricing service/store. It also
states the crucial consistency split: projected catalog content, live volatile
stock/price, and rebuildable derived stores.

The most important final-design refinement is to avoid ambiguity around price
in browse/search versus price in purchase. The final design can stay compact,
but it should mention "search uses a projected/bucketed price snapshot; detail
and checkout refresh/verify live price."

The edge cache is semantically useful, though the graph link `LB -> EdgeCache`
can read backwards. A CDN usually fronts the gateway (`Client -> EdgeCache ->
LB`) or sits in front of static/rendered catalog content. This is a diagram
polish issue rather than a design blocker.

## Concept Introduction and Learning Flow

The concept order is strong: CQRS first, then search/faceting, denormalized read
model, projection, consistency by data type, and finally scale/recovery. Each
step exposes the next problem naturally.

The dataset also does a good job introducing concepts only when they are needed.
Projection mechanics appear after read stores exist; live volatile reads appear
after projection exposes staleness; failure drills appear after the final
architecture is assembled.

The one concept that needs tighter placement is "price snapshot versus price
authority." It should appear in Step 3 or Step 4, before Step 6, because price
filtering/sorting is already part of search.

## Step-to-Final-Design Coherence

Coherence is now high:

- Step 2 establishes Catalog Service and Catalog Store as source of truth.
- Step 3 introduces Search Service, Search Index, and read-model hydration.
- Step 4 introduces the Product Read Model and product-detail flow.
- Step 5 introduces Change Stream and Indexer/Projector.
- Step 6 introduces Inventory and Pricing services with owned stores and live
  reads.
- Step 7 introduces EdgeCache, hotspot handling, and rebuild drills.
- Final design includes the components and links introduced across the steps.

The old review findings about missing `PriceDB`, missing live price edge,
missing product-detail price sequence, missing EdgeCache, and missing `LB` nodes
in Step 3/Step 4 are no longer valid for the current JSON.

## Realism Compared With Production Systems

The current dataset is realistic at the pattern and operational level. It
captures the production shape of a large catalog: source-of-truth writes,
derived search/read stores, CDC/outbox projection, shard/replica/cache scaling,
lag monitoring, and selective live reads for correctness-sensitive values.

The remaining realism gaps are marketplace-specific rather than general
architecture gaps. Real product catalogs need richer offer/buy-box semantics,
media pipelines, category taxonomy governance, abuse/moderation workflows,
ranking experimentation, personalized retrieval/ranking, review-summary
ownership, and checkout handoff. The dataset does not need to fully design all
of these, but it should name the most important boundaries so the candidate does
not accidentally claim catalog owns them all.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Step, option, and final-design link IDs resolve to
  `highLevelArchitecture.links`.
- View link endpoints are present in each view's `nodes` list; the previous
  Step 3/Step 4 `LB` omission is fixed.
- API and step-flow sequence messages reference declared participants.
- `satisfies[*].steps[*]` and `patterns[*].steps[*]` resolve to existing step
  IDs.
- High-level architecture node types are supported: `cache`, `client`,
  `database`, `edge`, `index`, `service`, `stream`, and `worker`.
- `satisfies.nonFunctional` has four entries while `requirements.nonFunctional`
  has five; add a mapping for the read-heavy requirement.
- `ReadModel` is typed as `cache`. This renders correctly, but semantically it
  is a persistent derived serving store. Consider `database`, or keep `cache`
  and preserve the current explicit language that it is rebuildable derived
  state rather than a volatile cache.
- The `edge-cache` link points from `LB` to `EdgeCache`. If the intended model
  is a fronting CDN, consider drawing `Client -> EdgeCache -> LB` with a local
  link in the Step 7/final-design views.
- `toProbeFurther.links` has a useful set of seven references covering
  Elasticsearch, Lucene, Bigtable, Dynamo, Debezium outbox, Kafka, and
  Percolator.

## Recommended Edits, Prioritized

### P1: Clarify price in search, facets, and sorting

State whether search price is a projected snapshot, bucketed range, winning
offer snapshot, or refreshed top-N value. Tie this to the high price/stock event
rate and to the live Pricing Service read.

### P1: Add a compact purchase-boundary note

Do not design checkout in full. Add two or three sentences explaining that cart
or checkout owns the final price quote and inventory reservation/hold, including
quote TTL and revalidation before order placement.

### P2: Scope multi-seller offers and buy-box behavior

Either declare the main walkthrough assumes one winning offer per product, or
add a compact offer summary model and describe how search/display price relates
to the selected offer.

### P2: Add the missing non-functional `satisfies` mapping

Map "Extremely read-heavy" to the CQRS, search/read model, and scaling steps.

### P2: Polish edge/cache semantics

Consider drawing the edge cache as a fronting CDN and add one failure drill for
stale cached content after moderation or a product suppression.

### P3: Add technology choices when this case gets a tech pass

This dataset has no `technologyChoices` section. That is optional, but a future
book polish pass could compare Elasticsearch/OpenSearch/Solr, Kafka/Pulsar,
Bigtable/Cassandra/DynamoDB, Redis/CDN cache choices, and managed cloud
equivalents.

## What Not To Change

- Keep the seven-step structure. It now teaches the system in the right order.
- Keep search/faceting as its own step; it is the product-catalog-specific
  teaching point.
- Keep the read model separate from the search index. Candidate answers often
  blur retrieval and hydration, and this dataset correctly separates them.
- Keep consistency-by-data-type as the senior insight. The current architecture
  supports it now.
- Keep checkout/order management out of scope; just define the handoff precisely.

## Bottom Line

The recent changes moved this dataset from "good but missing important
production support" to a strong product-catalog interview. The remaining work is
targeted: clarify how projected price participates in search, define the
purchase quote/reservation boundary, scope multi-seller offers, and fix the
small `satisfies.nonFunctional` mapping gap.
