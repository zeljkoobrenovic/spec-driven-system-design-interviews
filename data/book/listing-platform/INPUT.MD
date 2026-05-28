# Systems Design Interview Requirement: Listing Platform

## 1. Problem Statement

Design a large-scale **Listing Platform** that allows listing owners to publish, manage, enrich, validate, and distribute listings to seekers through a website and mobile app.

The platform supports multiple listing types, such as jobs, real estate, vehicles, services, products, or marketplace offers. For this interview, assume the listing model is generic, but extensible enough to support domain-specific fields.

The system must support:

1. Listing import from external systems via FTP.
2. Listing import from external systems via API.
3. Manual listing creation and editing inside the platform.
4. AI-assisted listing creation and editing.
5. Listing enrichment.
6. Fraud prevention and content quality checks.
7. Detection of duplicate imported listings.
8. Creation and maintenance of a search index for seekers.
9. Public website and mobile app for seekers.
10. Admin panel for listing owners and platform administrators.

---

# 2. Actors

## Listing Owner

A company, agency, partner, seller, or individual who owns listings and wants to publish them on the platform.

Listing owners can:

* Import listings through FTP.
* Import listings through API.
* Manually create listings.
* Edit, pause, delete, or republish listings.
* View validation errors.
* View listing performance metrics.
* Manage their organization, users, and permissions.

## External System

A third-party system used by a listing owner to manage listings externally.

Examples:

* Applicant tracking system.
* Real estate CRM.
* Dealer management system.
* Marketplace backend.
* Inventory management system.

External systems can:

* Upload files via FTP.
* Push listings via API.
* Update existing listings.
* Delete or expire listings.
* Retrieve import status and validation errors.

## Seeker

A public user searching for listings.

Seekers can:

* Search listings.
* Filter and sort results.
* View listing detail pages.
* Save listings.
* Report suspicious listings.
* Contact listing owners or apply/respond to listings.
* Use the website or mobile app.

## Platform Administrator

An internal operator who manages platform health, policies, fraud review, listing quality, and escalations.

Platform administrators can:

* Review flagged listings.
* Suspend listing owners.
* Override fraud decisions.
* Inspect import logs.
* Manage taxonomy, categories, enrichment rules, and moderation policies.
* Monitor system health.

---

# 3. Core Functional Requirements

## 3.1 Listing Import via FTP

The platform must allow listing owners and external systems to import listings using FTP or SFTP.

### Requirements

* Each listing owner can have one or more FTP accounts or directories.
* The platform must support scheduled file pickup.
* Supported file formats should include:

  * CSV
  * XML
  * JSON
  * Optionally compressed files such as ZIP or GZIP
* The platform must validate file structure before processing.
* The platform must support full and incremental imports.
* The platform must detect malformed files and report errors.
* The platform must provide import status:

  * Received
  * Parsing
  * Validating
  * Enriching
  * Duplicate checking
  * Fraud checking
  * Indexed
  * Partially failed
  * Failed
* Listing owners must be able to download import error reports.
* The system must be idempotent, so re-uploading the same file should not create duplicate listings.
* The system must support large files with millions of listings.
* Failed rows should not necessarily block successful rows unless configured by the owner.

### Design Considerations

Candidates should discuss:

* File watchers or scheduled ingestion jobs.
* Object storage for raw files.
* Streaming versus batch processing.
* Dead-letter queues for failed records.
* Import job metadata.
* Retry behavior.
* Schema versioning.
* File-level and row-level validation.

---

## 3.2 Listing Import via API

The platform must expose APIs that allow external systems to create, update, delete, and retrieve listings.

### Requirements

The API should support:

* Create listing.
* Update listing.
* Partial update listing.
* Delete or expire listing.
* Bulk import.
* Bulk status retrieval.
* Get validation errors.
* Get listing publication status.
* Webhook callbacks for import completion.

### API Characteristics

* APIs must be authenticated.
* APIs must be rate-limited.
* APIs must support idempotency keys.
* APIs must return meaningful validation errors.
* APIs must support asynchronous bulk processing.
* APIs must provide correlation IDs for debugging.
* APIs must support versioning.

Example endpoints:

```text
POST /api/v1/listings
PATCH /api/v1/listings/{listingId}
DELETE /api/v1/listings/{listingId}
POST /api/v1/listings/bulk
GET /api/v1/import-jobs/{jobId}
GET /api/v1/listings/{listingId}/status
```

### Design Considerations

Candidates should discuss:

* REST versus GraphQL versus event-driven ingestion.
* Synchronous versus asynchronous processing.
* Idempotency and deduplication.
* API gateway.
* Authentication using OAuth2, API keys, or mTLS.
* Rate limits per listing owner.
* Webhook retries and signature verification.

---

## 3.3 Manual Listing Creation in Platform

Listing owners must be able to create and edit listings through an admin panel.

### Requirements

The platform must provide:

* Listing creation form.
* Draft mode.
* Save and resume later.
* Required and optional fields.
* Field validation.
* Rich text editing.
* Image and media upload.
* Preview before publishing.
* Approval workflow if configured.
* Listing version history.
* Ability to clone existing listings.
* Ability to pause, archive, delete, or republish listings.

### AI Support

The manual editing process should include AI-assisted features such as:

* Generate listing title from description.
* Improve listing description.
* Suggest category.
* Suggest tags.
* Detect missing important fields.
* Rewrite for clarity.
* Normalize formatting.
* Translate listing content.
* Detect policy violations.
* Suggest price, salary, location, or metadata improvements where applicable.
* Identify potentially misleading or discriminatory language.

### Design Considerations

Candidates should discuss:

* Human-in-the-loop AI.
* Prompting and model safety.
* AI suggestion acceptance/rejection.
* Audit trail for AI-generated changes.
* Latency constraints for interactive editing.
* Cost control for AI usage.
* Caching AI suggestions.
* Guardrails against hallucinated information.

---

## 3.4 Listing Enrichment

The platform must enrich listings before publication and indexing.

### Enrichment Examples

The enrichment pipeline may include:

* Category classification.
* Tag extraction.
* Location normalization.
* Geocoding.
* Language detection.
* Translation.
* Image analysis.
* Price normalization.
* Salary normalization.
* Company or owner metadata enrichment.
* Taxonomy mapping.
* Keyword extraction.
* Quality score calculation.
* Completeness score calculation.
* SEO metadata generation.
* Expiration date prediction.
* Related listings detection.

### Requirements

* Enrichment should be configurable by listing type and owner.
* Enrichment should be asynchronous.
* Enriched fields must be distinguishable from owner-provided fields.
* The platform must preserve original imported data.
* Enrichment results should be versioned.
* Failed enrichment should not always block publication.
* Some enrichment failures may block publication, depending on policy.

### Design Considerations

Candidates should discuss:

* Pipeline orchestration.
* ML model serving.
* Batch and streaming enrichment.
* External enrichment providers.
* Confidence scores.
* Manual override.
* Reprocessing when enrichment logic changes.

---

## 3.5 Listing Fraud Prevention

The platform must prevent fraudulent, low-quality, misleading, or policy-violating listings from being published.

### Fraud Checks

Fraud prevention may include:

* Owner reputation scoring.
* Duplicate owner detection.
* Suspicious contact information detection.
* Scam phrase detection.
* Unusual pricing detection.
* Suspicious location mismatch.
* Banned keyword detection.
* Image reuse detection.
* External link reputation.
* Payment scam detection.
* Impersonation detection.
* Abnormal import behavior.
* High-frequency listing changes.
* User reports from seekers.
* Manual moderation review.

### Requirements

* Every listing must receive a fraud risk score.
* Listings above a configurable threshold should be held for review.
* Listings below a safe threshold can be auto-published.
* Suspicious owners may be rate-limited or suspended.
* Administrators must be able to review fraud decisions.
* The system must explain why a listing was flagged.
* The fraud system must support rule-based and ML-based signals.
* The system must log all fraud decisions for auditability.
* False positives and false negatives must be trackable.

### Design Considerations

Candidates should discuss:

* Real-time versus asynchronous fraud checks.
* Feature store.
* Rules engine.
* ML scoring service.
* Manual review queue.
* Feedback loop from moderator decisions.
* Adversarial behavior.
* Abuse prevention.
* Auditability and explainability.

---

## 3.6 Detection of Duplicate Imports

The platform must detect duplicate listings across repeated imports, multiple channels, and potentially across multiple listing owners.

### Duplicate Types

The system should detect:

* Exact duplicates.
* Same external listing imported multiple times.
* Same listing imported through FTP and API.
* Near-duplicates with small text differences.
* Duplicates across different listing owners.
* Reposted listings after expiration.
* Cloned listings with modified metadata.

### Matching Signals

Possible duplicate detection signals include:

* External listing ID.
* Listing owner ID.
* Title.
* Description.
* Location.
* Price or salary.
* Contact details.
* Images.
* URLs.
* Normalized metadata.
* Semantic embeddings.
* Content hashes.
* Geospatial proximity.
* Time window.

### Requirements

* The system must support deterministic deduplication using owner ID and external listing ID.
* The system should support fuzzy deduplication for near-duplicates.
* The system must define conflict resolution rules.
* The system must avoid incorrectly merging distinct listings.
* Duplicate decisions must be auditable.
* The system should support manual review of suspected duplicates.
* Deduplication must happen before indexing.
* Re-importing an unchanged listing should be idempotent.

### Design Considerations

Candidates should discuss:

* Hashing normalized listing content.
* Similarity search.
* Blocking strategies to reduce comparison cost.
* Embedding-based matching.
* Record linkage.
* Merge policies.
* Tombstones for deleted listings.
* External ID mapping table.

---

## 3.7 Search Index Creation for Seekers

The platform must create and maintain a search index for fast seeker search.

### Search Capabilities

Seekers should be able to:

* Search by keyword.
* Filter by category.
* Filter by location.
* Filter by price, salary, date, or other numeric ranges.
* Sort by relevance, newest, distance, popularity, or price.
* Search using autocomplete.
* Use synonyms and spell correction.
* View personalized or recommended listings.
* See only active, approved, non-fraudulent listings.

### Requirements

* Only publishable listings should be indexed.
* Search index must be updated when listings are created, edited, expired, paused, deleted, enriched, or moderated.
* The platform must support near-real-time indexing.
* The platform must tolerate temporary indexing lag.
* Indexing failures must be retried.
* The system must support reindexing all listings.
* The system must support multiple indices or index versions.
* The system must support blue-green index deployment.
* Search result ranking should account for:

  * Text relevance
  * Freshness
  * Listing quality
  * Fraud score
  * Owner reputation
  * User behavior
  * Geographic relevance

### Design Considerations

Candidates should discuss:

* Elasticsearch, OpenSearch, Solr, or managed search services.
* Event-driven indexing.
* Outbox pattern.
* Index schema evolution.
* Index rebuilds.
* Search ranking.
* Caching popular searches.
* Handling deleted listings.
* Consistency between source of truth and search index.

---

## 3.8 Website and Mobile App for Seekers

The platform must expose listings through a public website and mobile application.

### Requirements

The seeker experience should include:

* Home page.
* Search results page.
* Listing detail page.
* Filters and sorting.
* Map-based search where applicable.
* Saved listings.
* Recently viewed listings.
* Alerts for new matching listings.
* Share listing.
* Report listing.
* Contact or apply/respond to listing.
* Authentication for personalized features.
* Anonymous browsing for basic search.
* SEO-friendly listing pages for web.
* Deep links for mobile apps.

### Non-Functional Expectations

* Search results should load quickly.
* Listing detail pages should be cacheable.
* Public pages should be SEO optimized.
* The website should support high traffic spikes.
* The mobile app should use APIs optimized for mobile latency and bandwidth.
* The platform should support A/B testing and experimentation.
* The platform should collect analytics events.

### Design Considerations

Candidates should discuss:

* BFF layer for web and mobile.
* CDN caching.
* SSR or static rendering for SEO.
* API pagination.
* Infinite scrolling.
* Search result caching.
* Personalized recommendations.
* Event tracking.
* Abuse prevention for contact forms.

---

## 3.9 Admin Panel for Listing Management

The platform must provide an admin panel for listing owners and internal administrators.

### Listing Owner Admin Features

Listing owners should be able to:

* View all listings.
* Create and edit listings.
* Import listings.
* See import history.
* Download error reports.
* View listing status.
* View fraud or moderation status.
* Pause, archive, delete, or republish listings.
* Manage users and roles.
* Configure FTP/API integrations.
* Configure webhooks.
* View analytics and performance reports.

### Platform Admin Features

Internal administrators should be able to:

* Search all listings.
* View raw and enriched listing data.
* Review fraud flags.
* Override moderation decisions.
* Suspend listing owners.
* Inspect import jobs.
* Replay failed processing jobs.
* Manage taxonomy.
* Manage fraud rules.
* Manage enrichment rules.
* Trigger reindexing.
* View system dashboards.
* Audit user actions.

### Requirements

* Role-based access control is required.
* Admin actions must be audited.
* Sensitive fields must be protected.
* Listing owners must only access their own data.
* Platform admins may have broader access based on role.
* The system must support bulk actions.
* The system must support filtering by listing status.

---

# 4. Listing Lifecycle

A listing may move through the following states:

```text
Draft
Imported
Validation Failed
Validated
Enrichment Pending
Enriched
Duplicate Suspected
Fraud Review Pending
Rejected
Approved
Published
Indexed
Paused
Expired
Deleted
Archived
```

A simplified lifecycle:

```text
Create / Import
  -> Validate
  -> Normalize
  -> Enrich
  -> Deduplicate
  -> Fraud Check
  -> Approve / Reject / Review
  -> Publish
  -> Index
  -> Serve to Seekers
```

The candidate should discuss which steps are synchronous and which are asynchronous.

---

# 5. Data Model Requirements

The system should include entities such as:

## Listing

Core fields:

* listing_id
* owner_id
* external_listing_id
* source_channel: FTP, API, Manual
* title
* description
* category
* location
* price or salary
* contact information
* media
* status
* fraud_score
* quality_score
* duplicate_group_id
* created_at
* updated_at
* published_at
* expired_at

## ListingOwner

Fields:

* owner_id
* name
* account_status
* reputation_score
* billing status, if applicable
* integration configuration
* created_at

## ImportJob

Fields:

* import_job_id
* owner_id
* source_channel
* file_name
* status
* total_records
* successful_records
* failed_records
* duplicate_records
* started_at
* completed_at

## ImportRecord

Fields:

* import_record_id
* import_job_id
* row_number
* external_listing_id
* status
* error_message
* listing_id

## EnrichmentResult

Fields:

* enrichment_id
* listing_id
* enrichment_type
* output
* confidence_score
* model_version
* created_at

## FraudDecision

Fields:

* fraud_decision_id
* listing_id
* fraud_score
* triggered_rules
* model_version
* decision
* reviewer_id
* created_at

## DuplicateCandidate

Fields:

* listing_id
* candidate_listing_id
* similarity_score
* matching_signals
* decision
* created_at

## SearchDocument

Search-optimized representation of listing data.

## AuditLog

Fields:

* actor_id
* actor_type
* action
* entity_type
* entity_id
* old_value
* new_value
* timestamp

---

# 6. Non-Functional Requirements

## Scalability

The platform should support:

* Millions of active listings.
* Tens or hundreds of millions of historical listings.
* Thousands of listing owners.
* Large FTP imports.
* High API write throughput from partners.
* High read traffic from seekers.
* Search traffic spikes during peak periods.

## Availability

Suggested targets:

* Public seeker search: 99.9% or higher.
* Listing detail pages: 99.9% or higher.
* Import pipelines: eventually reliable, but may tolerate delay.
* Admin panel: lower availability may be acceptable than public search.

## Latency

Example targets:

* Search query latency: under 300 ms p95.
* Listing detail page API: under 200 ms p95.
* Manual listing save: under 500 ms p95.
* API single listing create/update: under 300 ms for accepted request.
* Bulk import processing: asynchronous.
* Indexing delay: under a few minutes for most listings.

## Consistency

The system can use different consistency models:

* Strong consistency for listing ownership, permissions, and billing-related changes.
* Eventual consistency for search indexing.
* Eventual consistency for enrichment.
* Strong or transactional consistency for manual edits and listing state transitions.

## Reliability

The system must support:

* Retries.
* Dead-letter queues.
* Idempotency.
* Backpressure.
* Replayable events.
* Import recovery.
* Search reindexing.
* Disaster recovery.

## Security

The platform must provide:

* Authentication.
* Authorization.
* Role-based access control.
* API key management.
* OAuth2 support for external systems.
* Secure FTP or SFTP.
* Encryption in transit.
* Encryption at rest.
* Secret management.
* Audit logs.
* Rate limiting.
* Input sanitization.
* Protection against scraping and spam.

## Privacy and Compliance

Depending on region and listing type, the platform may need:

* GDPR compliance.
* Data retention policies.
* Right to deletion.
* PII protection.
* Consent management.
* Moderation audit history.
* Access controls for sensitive contact data.

## Observability

The system must provide:

* Metrics.
* Logs.
* Traces.
* Import job dashboards.
* Fraud decision dashboards.
* Search quality dashboards.
* Indexing lag dashboards.
* Alerting on failures.
* Dead-letter queue monitoring.
* API usage dashboards per owner.

---

# 7. Suggested High-Level Architecture

A strong candidate may propose an architecture similar to this:

```text
External Systems
   | 
   |-- FTP Uploads
   |-- API Calls
   v
Ingestion Layer
   |
   |-- File Parser
   |-- API Gateway
   |-- Validation Service
   v
Message Queue / Event Bus
   |
   v
Listing Processing Pipeline
   |
   |-- Normalization Service
   |-- Enrichment Service
   |-- Duplicate Detection Service
   |-- Fraud Detection Service
   |-- Moderation Service
   v
Listing Store
   |
   v
Publishing Service
   |
   v
Search Indexer
   |
   v
Search Engine
   |
   v
Website / Mobile App / Seeker APIs
```

Supporting systems:

```text
Admin Panel
Analytics Platform
Audit Log Service
Notification Service
AI Assistance Service
Media Service
Identity and Access Management
Monitoring and Alerting
```

---

# 8. Key Design Questions for the Candidate

## Ingestion

* How would you design FTP ingestion for very large files?
* How would you avoid duplicate imports?
* How would you support both full and incremental imports?
* How would you handle partially failed imports?
* How would external systems check import status?

## Data Model

* What is the source of truth for listing data?
* How do you model owner-provided versus enriched fields?
* How do you represent listing lifecycle states?
* How do you handle versioning and audit trails?

## Processing Pipeline

* Which operations happen synchronously?
* Which operations happen asynchronously?
* How do you guarantee idempotency?
* How do you replay failed events?
* How do you handle backpressure?

## Duplicate Detection

* How do you detect exact duplicates?
* How do you detect near duplicates?
* How do you avoid false merges?
* How do you handle duplicates across different owners?

## Fraud Prevention

* What signals would you use?
* How would you combine rules and ML?
* How would you handle manual review?
* How would you prevent adversarial abuse?
* How would you measure false positives and false negatives?

## Search

* How do you keep the search index updated?
* What fields are indexed?
* How do you support filtering and ranking?
* How do you handle reindexing?
* How do you keep search fast under high traffic?

## AI Assistance

* Where would AI features fit into the architecture?
* How do you make AI suggestions safe and auditable?
* How do you avoid hallucinated listing details?
* How do you control AI latency and cost?

## Admin and Permissions

* How would you design RBAC?
* How do you separate listing owner admin access from platform admin access?
* How do you audit admin actions?
* How do you support bulk listing operations?

## Reliability

* What happens if enrichment fails?
* What happens if fraud scoring is unavailable?
* What happens if search indexing fails?
* How do you recover from a bad import?
* How do you roll back bad enrichment or fraud rules?

---

# 9. Possible Deep-Dive Areas

For a 60-minute interview, the interviewer can pick one or two areas to explore deeply:

1. **Ingestion and import pipeline**
2. **Search indexing and seeker search**
3. **Duplicate detection**
4. **Fraud prevention**
5. **AI-assisted listing creation**
6. **Listing lifecycle and state management**
7. **Admin panel and owner workflows**
8. **Event-driven architecture and reliability**

---

# 10. Expected Candidate Output

A strong candidate should produce:

* Clarifying questions.
* Functional and non-functional requirements.
* High-level architecture.
* Data model.
* API design.
* Processing pipeline.
* Deduplication strategy.
* Fraud prevention strategy.
* Search indexing strategy.
* Scalability and reliability discussion.
* Tradeoffs and failure handling.

---

# 11. Example Clarifying Questions

A candidate may ask:

* What type of listings are we supporting?
* How many active listings are expected?
* How many listing owners are expected?
* What is the expected import volume per day?
* How fresh does the search index need to be?
* Are listings paid, free, or both?
* Are all listings public?
* Is moderation required before publication?
* Do seekers need accounts?
* Do we need recommendations or only search?
* Are external systems trusted?
* Are duplicate listings allowed in some cases?
* What are the fraud consequences?
* What regions and compliance requirements apply?
* Do listing owners require analytics?
* Is there a monetization or ranking component?

---

# 12. Optional Scale Assumptions for Interview

To make the problem concrete, the interviewer may provide these assumptions:

* 10 million active listings.
* 500 million historical listings.
* 50,000 listing owners.
* 5,000 FTP imports per day.
* 100 million API write requests per month.
* 50 million seeker searches per day.
* 5 million listing detail views per day.
* Search index freshness target: 5 minutes.
* Fraud review SLA: 24 hours.
* Duplicate detection should run before publication.
* Public search should remain available even if ingestion is degraded.

---

# 13. Example Evaluation Criteria

## Strong Signals

A strong candidate:

* Separates source-of-truth storage from search index.
* Uses asynchronous pipelines for import, enrichment, fraud, and indexing.
* Handles idempotency carefully.
* Considers external IDs and content hashes for deduplication.
* Understands search indexing tradeoffs.
* Designs fraud prevention as both rules-based and ML-based.
* Includes manual review and auditability.
* Designs for partial failures and retries.
* Mentions backpressure and dead-letter queues.
* Thinks about RBAC and tenant isolation.
* Discusses observability and operational dashboards.

## Weak Signals

A weak candidate:

* Treats the search index as the source of truth.
* Ignores duplicate imports.
* Assumes all imports are small.
* Makes all processing synchronous.
* Does not handle partial failures.
* Ignores fraud or moderation workflows.
* Does not discuss idempotency.
* Does not consider indexing lag.
* Ignores permissions and tenant boundaries.
* Provides only UI features without backend design.

---

# 14. Follow-Up Interview Prompts

The interviewer can ask:

1. “How would your design change if FTP imports contain 10 million rows?”
2. “How would you detect that the same listing came through FTP yesterday and API today?”
3. “How would you prevent fraudulent listings from appearing in search?”
4. “How would you rebuild the entire search index without downtime?”
5. “How would you let listing owners see why their listing was rejected?”
6. “How would you handle a bug that incorrectly marks 1 million listings as duplicates?”
7. “How would you roll out a new enrichment model safely?”
8. “How would you support multiple listing domains with different schemas?”
9. “How would you prevent search result scraping?”
10. “How would you design the admin audit log?”

---

# 15. Condensed Interview Prompt

Use this shorter version when giving the problem to a candidate:

> Design a scalable listing platform that allows listing owners to import listings through FTP and API, manually create and edit listings with AI assistance, enrich listings, detect duplicates, prevent fraud, publish valid listings to a search index, and expose them to seekers through a website and mobile app. The system must also include an admin panel for listing owners and platform administrators. Discuss functional requirements, non-functional requirements, architecture, data model, APIs, processing pipeline, search indexing, deduplication, fraud prevention, and operational concerns.
