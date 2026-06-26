# Internal Developer Platform (IDP) — Interview Build Plan

This is the authoring plan for the `data/book/internal-developer-platform/`
dataset. It maps the source material (`INPUT.pdf` — Humanitec's *"Create your own
platform reference architecture"* template) plus deep web research into the
interview schema (`PLAN.md` at repo root). Build `interview.json` to match the
shape and depth of `data/book/cicd-pipeline/` and `data/book/payment-system/`.

> **Why this case is different from the others.** Most cases in the book design a
> *product* (a feed, a payment, a search index). This one designs the *platform
> that other engineers build products on*. The "users" are internal developers;
> the "non-functional requirements" are developer experience, cognitive load, and
> deploy velocity; and the central architectural move is an **abstraction** (a
> developer-facing workload spec) backed by an **orchestrator** that turns intent
> into concrete infrastructure. Keep that framing front and center — it is the
> thing interviewers actually probe.

---

## 0. Source material — what `INPUT.pdf` gives us

The PDF is the Humanitec / platformengineering.org **5-plane reference
architecture** template (AWS, GCP, Azure, and multi-cloud variants, plus a
"platform tools" catalog of real products per category). It is the canonical
community model for an IDP. We adopt its structure as the backbone of the
interview because it is (a) widely recognized, (b) tool-agnostic, and (c) maps
cleanly to "planes" that become natural architecture steps.

**The five planes (this is the spine of the whole interview):**

| Plane | What it is | Sub-categories (from the PDF) |
|---|---|---|
| **Developer Control Plane** | Where developers declare intent and interact day-to-day | IDE/CDE · Copilots/Agents/LLM · Portal · (Workload/App Specification — *Score*) |
| **Integration & Delivery Plane** | Turns source + spec into a deployed, running state | Version Control · Services/App Specification (Score) · Platform/Infra-as-Code · CI · CD · Registry · **Platform Orchestrator** |
| **Resource Plane** | The actual infrastructure and backing services | Compute · Cluster Management · Data · Networking · Services/Messaging |
| **Observability Plane** | Operational insight into apps and infra | Monitoring & Logging · Observability (tracing) · FinOps · Incident Management |
| **Security Plane** | Secrets, identity, and policy enforcement | Code Analysis · Secrets · ID Management · Policy Control · Network Security · Security Suites |

> **The Platform Orchestrator is the heart of the model.** It reads the
> developer's workload spec on every `git push`, *matches* each requested abstract
> resource (e.g. `postgres`) to environment-specific **Resource Definitions**
> (e.g. RDS in prod, a container locally), invokes **Drivers** that provision the
> real thing, and wires the outputs (host, port, credentials) back into the
> workload. This is **Dynamic Configuration Management**: config is *generated
> fresh per deploy per environment* instead of hand-maintained. That single idea
> is what separates a real IDP from "Backstage + a pile of Helm charts."

> **A note on accuracy / vendor spin.** The IDP space is dominated by
> vendor-authored content (Humanitec, Port, vCluster). The research below flags
> which claims are independently verified vs. vendor worked-examples. In the
> dataset, prefer the *mechanism* (config-as-data, per-deploy generation) over
> the *marketing number* ("95% fewer config files" is a Humanitec worked-example,
> not a benchmark — cite it as a claim, not a fact). The single most
> credibility-building fact to include: **DORA 2024 found IDPs raised individual
> productivity (+6%) but could *decrease* delivery throughput (−8%) and stability
> (−14%)** — a measured tradeoff, not the "platforms always make you faster"
> story. Including it signals we know the literature isn't all hype.

---

## 1. Framing (`title`, `description`)

- **title:** `"Internal Developer Platform (IDP) — System Design"`
- **description:** One paragraph. Themes to hit: design the platform internal
  developers build on; the core move is a **developer-facing workload abstraction
  (Score-style spec)** backed by a **Platform Orchestrator** that turns intent
  into concrete cloud resources per environment; organized as **five planes**
  (Developer Control, Integration & Delivery, Resource, Observability, Security);
  the hard parts are *config drift vs. dynamic configuration*, *golden paths vs.
  flexibility*, *self-service vs. ticket-ops*, *multi-tenancy/isolation*, and
  *adoption* (a platform nobody uses is a failed platform). Treat the platform
  **as a product**.

- **icon:** reuse a platform/gear-style `icon.png` (match sibling datasets;
  `assets.icon = "icon.png"`).

---

## 2. Requirements (`requirements`, `requirementsDiagram`)

Frame requirements around **internal developers as the users** and **platform
engineers as the operators**.

**Functional**
- A developer can declare *what* a service needs (container + abstract resources
  like a database, a queue, DNS, a route) in **one spec**, without writing
  cloud-specific config.
- Self-service: a developer can create a new service from a **golden path**
  (scaffolds repo + CI/CD + observability + ownership) and deploy it to dev in
  minutes — no ticket to the platform team.
- The platform provisions and binds backing resources automatically per
  environment (dev/staging/prod), injecting connection details and secrets.
- On-demand **ephemeral/preview environments** (e.g. one per pull request),
  auto-torn-down.
- A **software catalog** lists every service, owner, docs, dependencies, and
  health.
- Progressive delivery + rollback are wired in by default (GitOps).
- Platform engineers can define/version golden paths and resource definitions,
  and roll out org standards (e.g. mandatory APM sidecar) without per-team edits.

**Non-functional** (this is where the case is unusual — DevEx *is* the SLO)
- **Low cognitive load** for developers; they should not need to learn
  Kubernetes/Terraform to ship. (Team Topologies thesis.)
- **Fast time-to-first-deploy** (minutes, not days) and **fast onboarding** of a
  new developer.
- **No config drift**: every environment is reproducible from declared state.
- **Self-service, not ticket-ops** — the platform must not become a queue.
- **Multi-tenant isolation** between teams (namespaces/RBAC/quotas; harder
  isolation for regulated workloads).
- **Adoption is a first-class NFR**: golden paths must be *paved roads with escape
  hatches*, not mandated cages — measure voluntary adoption.
- **Reliability of the platform itself**: the orchestrator/control plane is a
  shared failure domain — a build/deploy outage blocks every team.
- **Measurable**: DORA metrics, DevEx/SPACE, adoption rate, time-to-first-deploy.

**`requirementsDiagram`** (raw Mermaid `graph LR`, simple sketch): Developer →
Workload Spec → Orchestrator → (Resources / Pipeline / Portal), with Platform
Engineer → Golden Paths / Resource Definitions feeding the orchestrator. Keep it
metric-free and minimal (per repo convention for requirements/capacity diagrams).

---

## 3. Capacity / sizing (`capacity`, `capacityDiagram`)

This is an *organizational* sizing exercise, not packets-per-second. Use realistic,
sourced numbers (flag vendor vs. independent). Suggested rows:

| label | value | note |
|---|---|---|
| Internal developers served | ~300–1,500 | Adidas ~300 eng / 35-person platform team; GitHub internal ~1,300 eng |
| Services / components in catalog | hundreds–thousands | Spotify: "tens of thousands of components," 700 R&D squads, 120+ plugins |
| Deploys per day | dozens–hundreds | Adidas: from every 4–6 weeks → 3–4×/day after platform |
| Kubernetes clusters | tens–hundreds | Mercedes-Benz: ~900 clusters, ~12 platform engineers |
| Platform team : developers ratio | ~1:15–1:20 | Practitioner heuristic; first team 3–5 engineers |
| Time-to-first-deploy target | minutes | vs. days of ticket-ops; onboarding a new dev in <1 hr (vendor) |
| Ephemeral env lifetime | hours–days | One per PR; ~76% of non-prod is idle → reaper needed |
| Config files (before → after) | 300+ → ~10 | 10 svc × 4 env worked-example; Humanitec "up to 95% fewer" *(vendor claim)* |

**`capacityDiagram`**: optional simple `graph LR` showing the fan-out (1 spec →
N environments → M resources). Keep simple.

> Be explicit in notes which numbers are independently reported (Adidas K8s case
> study, Mercedes-Benz/InfoWorld, DORA, Spotify open-source) vs. vendor
> worked-examples (Humanitec config reduction, "24-min MVP", onboarding times).

---

## 4. API / interfaces (`api`)

The "API" of an IDP is the **developer contract**, not REST CRUD. Model these:

- **The workload spec** (`score.yaml`-style) — the primary developer interface.
  Show a realistic Score example: `metadata`, `containers` (image, env), `service`
  (ports), `resources` (a `postgres`, a `dns`, a `route`) declared abstractly with
  `${resources.db.host}`-style placeholders resolved per environment. Add a
  `sequence` for "developer `git push` → orchestrator deploy."
- **`POST /workloads/{id}/deploy`** (or "git push triggers it") — submit spec,
  orchestrator matches resources, generates config, deploys. Include a sequence:
  Developer → CI → Orchestrator → (Resource Definitions → Drivers → cloud) →
  Runtime.
- **`POST /scaffolder/templates/{name}`** — create a new service from a golden
  path (Backstage Scaffolder–style): scaffolds repo, CI, catalog entry, ownership.
- **Software catalog query** — `GET /catalog/components`, ownership, relations.
- **Resource Definition registration** (platform-engineer-facing) — register how
  an abstract resource type is fulfilled per environment.
- **Ephemeral environment lifecycle** — `POST /environments` (per PR) /
  auto-delete on close.

Keep request/response bodies short and realistic. Put per-endpoint flows in
`api[].sequence` (they surface in the Wrap-up API Flows entry).

---

## 5. Data model (`dataModel`)

The platform's *control-plane* state (not application data):

- **Workload / Application** — id, owner team, repo, current spec version.
- **Workload Spec (Score)** — versioned; container(s), service ports, abstract
  resource requests.
- **Environment** — dev/staging/prod/ephemeral; cluster/namespace binding;
  lifecycle (permanent vs. ephemeral + TTL).
- **Resource Definition** — abstract type (`postgres`) → driver + per-environment
  matching rules (env, project, resource class).
- **Resource (provisioned instance)** — concrete resource (an RDS instance),
  outputs (host/port/secret ref), owning deployment, lifecycle.
- **Deployment / Release** — workload × environment × spec version; status; the
  generated config set; rollout strategy.
- **Catalog Component** — service metadata, owner, links, dependencies, health.
- **Golden Path / Template** — versioned scaffolder template + the standards it
  bakes in.

Auto-ER from `dataModel` (don't hand-author Mermaid ER unless needed).

---

## 6. Patterns (`patterns`) — dataset-level, grouped

Reusable platform-engineering patterns, each `{ name, group, what, whenToUse,
steps }` cross-linked to the steps that use them:

- **Group: Developer abstraction**
  - *Workload specification (Score)* — declare what, not how.
  - *Separation of concerns (dev "what" / platform "how")*.
  - *Dynamic Configuration Management* — generate config per deploy, not static
    templates.
- **Group: Self-service & paved roads**
  - *Golden paths / paved roads* — the supported, best-practices-baked way.
  - *Platform-as-a-Product* — internal devs as customers; adoption as the metric.
  - *Thinnest Viable Platform (TVP)* — build the minimum that accelerates teams.
  - *Software catalog* — single inventory of components + ownership.
- **Group: Delivery & infra**
  - *GitOps* — Git as source of truth; reconcile live state to it.
  - *Control-plane reconciliation vs. apply-time IaC* (Crossplane vs. Terraform).
  - *Environment-as-a-Service / ephemeral environments*.
- **Group: Operations & guardrails**
  - *Policy-as-code* (OPA/Kyverno guardrails, not gates).
  - *Multi-tenancy via namespaces + RBAC + quotas* (soft isolation by default).

---

## 7. Architecture steps (`steps`) — the naive → better arc

The build order follows the **maturity progression** the research surfaced: each
stage breaks under load and *forces* the next. This is the interview's narrative
spine. Aim for ~8 top-level steps (plus 1 sub-step), most with `options`,
`recap`, `traps`, `flows` where temporal, `interviewerSignals`, and `concepts`.

> Each step's `view` builds on the previous one's nodes (the highlight pipeline
> auto-diffs new nodes). Define all nodes/links once in `highLevelArchitecture`
> and reference them by id in each `view`.

**Step 1 — Startup mode: a wiki, runbooks, and self-serve (stage zero)**
- *What:* No platform, no platform team. Developers themselves follow a wiki
  runbook and provision by hand (`dev-wiki`, `dev-k8s`). Frame it as a *legitimate*
  Thinnest Viable Platform, not a failure.
- *Forcing function:* runbooks rot, manual steps drift between engineers, a
  fat-fingered step takes prod down, no audit trail → the org adds an ops
  gatekeeper, which becomes step 2's queue.
- `traps`: "build a full IDP on day one (Google envy)"; "let the wiki stay the
  long-term source of truth."

**Step 2 — Growing pains: tickets, shared scripts, and an ops gatekeeper**
- *What:* The team grew and self-serve caused outages, so changes now route
  through an ops team via tickets; ops runs the same runbook by hand. No options
  — this is the bottleneck strawman.
- *Forcing function:* ticket-ops bottleneck — the queue grows linearly with
  adoption; lead times in days. (CNCF "Provisional" level.)
- `recap.newRisk`: every new service multiplies ops toil.
- `traps`: "rename Ops to 'platform team' without removing the ticket queue."

**Step 3 — Automate delivery: CI/CD + Helm charts per service**
- *What:* Pipelines build/test/deploy; Helm bundles manifests; copy-paste a chart
  per new service.
- *Forcing function:* **YAML sprawl → config drift**. 10 services × 4 envs = 300+
  config files; copies drift from declared state.
- `options`: CI choice (GitHub Actions vs. GitLab CI vs. Jenkins); GitOps CD
  (Argo CD vs. Flux — Argo has a UI + ApplicationSet for multi-tenant/preview;
  Flux is composable, RBAC-only, no UI).
- `traps`: "templating your way out of drift" — more Helm ≠ less drift.

**Step 3 — A self-service portal over existing tooling (Backstage)**
- *What:* Software catalog + scaffolder golden-path templates + docs + ownership.
- *Forcing function:* **"A portal is not your platform"** — it's a
  discovery/interaction layer; developers can *find* and *scaffold* but still
  can't *provision* infra. Build vs. buy: Backstage (framework, 6–12 mo, 2–5 FTE)
  vs. Port/Cortex/OpsLevel (SaaS) vs. Red Hat Developer Hub (supported Backstage).
- `options`: self-host Backstage vs. SaaS portal vs. managed Backstage.
- `concepts`: software catalog, golden path, scaffolder, platform-as-a-product.
- `traps`: "build the front-end first / confuse the portal with the platform."

**Step 4 — The workload spec + Platform Orchestrator (the key abstraction)**
- *What:* Introduce a Score-style spec (declare *what*) and an orchestrator that
  matches abstract resources → Resource Definitions → Drivers, and **generates
  config per deploy per environment** (RMCD: Read-Match-Create-Deploy).
- *Forcing function:* per-env hand-maintained config doesn't scale; conventional
  CD only "updates images in pre-existing environments."
- *This is the climax step.* Spend the most depth here. `flows`: developer
  `git push` → CI → orchestrator reads spec → matches resource defs → drivers
  provision → outputs injected → deployed.
- `options`: **Humanitec** (SaaS, graph-based, SLA) vs. **Kratix** (self-operated,
  K8s-API interface) vs. **Crossplane** (control-plane IaC underneath) vs.
  **Score + own controllers / GitOps-only**.
  - **Sub-step 4a — IaC engine under the orchestrator**: Terraform (BSL since Aug
    2023; IBM acquired HashiCorp Feb 2025) vs. **OpenTofu** (LF fork, MPL) vs.
    **Pulumi** vs. **Crossplane** (continuous reconciliation/drift-correction as
    K8s controllers vs. apply-time CLI — the cleanest IaC tradeoff to teach).
- `concepts`: Platform Orchestrator, Resource Definition, Driver, Dynamic
  Configuration Management, config-as-data.
- `traps`: over-abstraction / "golden cage"; leaky abstraction (5-min deploy,
  4-hr debug of a wrapper that hides the real K8s error); orchestrator as a single
  point of failure.

**Step 5 — The Resource Plane: compute, data, networking, messaging**
- *What:* What the orchestrator actually provisions into. Kubernetes compute,
  managed databases, DNS/ingress, queues. Multi-tenancy/isolation lives here.
- `options`: **multi-tenancy model** — namespace-per-team + RBAC + NetworkPolicy +
  quotas (soft, adequate for trusting internal teams) vs. cluster-per-tenant vs.
  **vcluster** (virtual control plane per tenant; for untrusted/regulated). Cite
  the neutral K8s multi-tenancy doc, not just vCluster-authored claims.
- `concepts`: soft vs. hard multi-tenancy, Environment-as-a-Service.

**Step 6 — Ephemeral / preview environments + golden-path versioning**
- *What:* On-demand env per PR (Argo CD ApplicationSet PR generator; vcluster),
  auto-teardown. Version golden paths with semver; v2 breaking changes are
  *opt-in*; don't force 100% migration.
- *Forcing function:* PR-close cleanup alone leaks cost → need an external reaper
  (CronJob) for stale envs; rigid golden path frustrates power users → escape
  hatches.
- `traps`: ephemeral env cost blow-up (no reaper); mandated migration; railroad vs.
  guardrail.

**Step 7 — Observability + Security planes; measuring platform success**
- *What:* Bake observability (metrics/logs/traces, FinOps, incident mgmt) and
  security (secrets via Vault/OpenBao/cloud KMS + External Secrets Operator;
  policy via OPA/Gatekeeper vs. Kyverno; ID; code analysis) into the golden path
  so every service gets them by default. Then **measure**: DORA, DevEx/SPACE,
  adoption rate, time-to-first-deploy, cognitive load.
- *Key honest beat:* DORA 2024's measured tradeoff (+6% productivity, but −8%
  throughput / −14% stability) — platforms are not a free win; you optimize for
  developer time and measure outcomes, not vanity metrics (portal logins).
- `concepts`: DORA, SPACE, DevEx, FinOps, policy-as-code, secret injection.
- `traps`: vanity metrics; mandated adoption / platform-as-a-gate; ivory-tower
  team that doesn't dogfood.

---

## 8. Final design (`finalDesign`)

A single `view` assembling the **full 5-plane reference architecture** — the
payoff diagram that mirrors the PDF's "Internal Developer Platform on Multicloud"
slide. Optionally one `options` entry ("Recommended assembly") with pros/cons.
Use `view.groups` (`highLevelArchitecture.types`) to draw the five planes as
labeled subgraphs:
- `developer-control-plane`, `integration-delivery-plane`, `resource-plane`,
  `observability-plane`, `security-plane`.
Description: how a `git push` flows through the planes and back as telemetry.

---

## 9. Wrap-up sections

- **`satisfies`** — map each functional/non-functional requirement to the steps
  that satisfy it (self-service → steps 3–4; no config drift → step 4; isolation →
  step 5; ephemeral envs → step 6; measurable/DevEx → step 7).
- **`technologyChoices`** — one entry per architecture concern, self-hosted vs.
  cloud, with `tradeoff` and `makesIrrelevant`. Cover: **Portal** (Backstage /
  RHDH / Port·Cortex·OpsLevel), **Orchestrator** (Humanitec / Kratix / Crossplane
  / Score+controllers), **IaC** (Terraform / OpenTofu / Pulumi / Crossplane), **CI**
  (GH Actions / GitLab CI / Jenkins), **CD/GitOps** (Argo CD / Flux), **Registry**
  (Harbor / ECR·Artifact Registry·GHCR), **Secrets** (Vault / OpenBao / cloud KMS +
  External Secrets Operator — *ESO + cloud KMS makes self-hosted Vault optional*),
  **Policy** (OPA·Gatekeeper / Kyverno), **Compute** (EKS/GKE/AKS), **Observability**
  (Prometheus·Grafana / Datadog / cloud-native), **Multi-tenancy** (namespaces+RBAC /
  vcluster). Run `_scripts/assign_tech_icons.py` after authoring to attach icons.
- **`interviewScript`** — what to say across phases (scope, requirements, the
  workload-spec abstraction pitch, the orchestrator deep dive, tradeoffs, wrap-up).
- **`levelVariants`** — Junior/Senior/Staff. Junior: name the planes and the tools.
  Senior: design the workload-spec → orchestrator → resource-definition flow and
  justify build/buy. Staff: platform-as-a-product, adoption strategy, org/team
  topology, measuring success, and the honest DORA tradeoff.
- **`followUps`** — e.g. "How do you migrate 200 services onto the platform without
  a big-bang?", "How do you keep the orchestrator from being a SPOF?", "How do you
  decide what *not* to abstract?", "What's your golden-path deprecation policy?"
- **`toProbeFurther`** — the citations in §11, as grouped links; cross-link from
  steps via `step.probeLinks[]`.

---

## 10. Common traps (woven into `step.traps` and the patterns)

Pull from the anti-pattern research. The strongest, each `{ trap, why, instead }`:

1. **Ticket-ops in disguise** — renaming Ops without removing the request queue;
   the queue grows with adoption → *self-service that eliminates tickets.*
2. **Portal = platform confusion** — a catalog can't provision infra → *add the
   orchestrator/automation underneath; a clunky CLI that automates a 3-hr task
   beats a pretty portal that does nothing.*
3. **Golden cage / over-abstraction** — designed for control, not consumption →
   *paved road WITH escape hatches; solve the 80% case.*
4. **Leaky abstraction** — wrapper hides the real error → *surface underlying
   errors transparently.*
5. **Config drift via more templating** — copy-paste Helm doesn't fix drift →
   *config-as-data, generate per deploy.*
6. **Mandated adoption / platform-as-a-gate** — forced use hides feedback, breeds
   shadow tooling → *voluntary pull; low adoption is a product bug.*
7. **Field of Dreams** — build comprehensively in isolation → *treat devs as
   customers; MVP one high-friction problem first.*
8. **Ephemeral env cost blow-up** — no reaper for stale envs → *external TTL
   reaper, not just PR-close cleanup.*
9. **Control plane as SPOF** — orchestrator down = all deploys stop → *failure
   isolation; decouple build from deploy.*
10. **Vanity metrics** — portal logins, API counts → *DORA + DevEx + adoption +
    time-to-first-deploy.*
11. **No dogfooding / ivory tower** — team has admin bypass, "works fine for us" →
    *structurally dogfood under the same constraints as developers.*

---

## 11. Citations (`toProbeFurther.links`)

Group as e.g. **Foundational models**, **The orchestrator & workload spec**,
**Self-service & team topology**, **Measuring platforms**, **Tools & tradeoffs**.
Each link: `{ id, group, title, url, source, type, year, why }`.

**Foundational models**
- CNCF Platforms White Paper — CNCF TAG App Delivery / Platforms WG, 2023 —
  https://tag-app-delivery.cncf.io/whitepapers/platforms/ — vendor-neutral
  definition of "platform" + capability domains.
- CNCF Platform Engineering Maturity Model — CNCF, 2023/2024 —
  https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/ —
  Provisional → Operational → Scalable → Optimizing (only ~13% reach Optimizing).
- Humanitec — "How to build an Internal Developer Platform" / reference
  architectures — 2024 — https://humanitec.com/blog/how-to-build-an-internal-developer-platform
  and https://github.com/humanitec-architecture — the 5-plane model + working IaC.
- Team Topologies (core team types; Thinnest Viable Platform) — Skelton & Pais,
  2019 — https://teamtopologies.com/key-concepts-content/what-are-the-core-team-types
  — platform/enabling/stream-aligned teams; cognitive-load thesis; TVP.

**The orchestrator & workload spec**
- Score — score.dev docs + score-spec/spec — CNCF Sandbox (Jul 2024) —
  https://docs.score.dev/ , https://github.com/score-spec/spec — the workload spec
  (metadata/containers/service/resources); `score-compose` / `score-k8s`.
- "What is a Platform Orchestrator?" — CNCF, 2022 —
  https://www.cncf.io/blog/2022/08/04/what-is-a-platform-orchestrator/ — the
  read-match-create-deploy mechanism + dynamic config.

**Self-service & team topology**
- Backstage — Spotify / CNCF — https://backstage.io/ ,
  https://backstage.spotify.com/discover/backstage-101 — software catalog,
  scaffolder, golden paths.
- "Backstage is not your platform" — platformengineering.org — the portal-vs-
  platform distinction.
- Netflix — "Full Cycle Developers" / paved road (supported, not mandated) — 2018 —
  https://netflixtechblog.com/full-cycle-developers-at-netflix-a08c31f83249

**Measuring platforms**
- DORA metrics + DORA 2024 report — Google/DORA —
  https://dora.dev/research/2024/dora-report/ — the +6% productivity / −8%
  throughput / −14% stability platform tradeoff (the credibility-maker).
- SPACE framework — ACM Queue, 2021 — https://queue.acm.org/detail.cfm?id=3454124
- DevEx — GetDX / ACM Queue, 2023 — https://getdx.com/report/devex-productivity/

**Tools & tradeoffs (build/buy)**
- Crossplane vs. Terraform/Pulumi (control-plane vs. apply-time) — Pulumi docs —
  https://www.pulumi.com/docs/iac/comparisons/crossplane/ ; Crossplane graduated
  CNCF Nov 2025.
- Terraform → BSL (Aug 2023) + OpenTofu fork —
  https://www.hashicorp.com/blog/hashicorp-adopts-business-source-license ; IBM
  closed HashiCorp acquisition Feb 2025.
- Argo CD vs. Flux — Codefresh —
  https://codefresh.io/learn/argo-cd/argo-cd-vs-flux-6-key-differences-and-how-to-choose/
- External Secrets Operator — https://external-secrets.io/ ; Vault → BSL / OpenBao.
- Kyverno vs. OPA/Gatekeeper — Nirmata; Kyverno graduated CNCF Mar 2026.
- Real-scale case studies — Adidas (Kubernetes case study,
  https://kubernetes.io/case-studies/adidas/) and Mercedes-Benz (~900 clusters,
  InfoWorld 2024). *Note: Adidas deploy-frequency numbers are the K8s story, not a
  Backstage talk — don't conflate.*
- Gartner — 80% of large software orgs to have platform teams by 2026 (from 45% in
  2022) — context stat for "why this matters."

---

## 12. Visual assets (optional, post-authoring)

Once `interview.json` is complete and validated, optionally generate visuals with
the `_scripts/` generators (per repo convention):
- `generate_diagram_picture.py` → per-step/option AI visuals (toggled by the
  Diagram | AI Visual tab).
- `generate_design_vs_requirements_pictures.py` → per-requirement illustrations.
- `generate_interview_comic.py` → the Explainer Comic (Wrap-up).
- `assign_tech_icons.py <interview.json>` → tech-choice chip icons.
Then run `python3 build.py` and `python3 downsize-images.py docs/`.

---

## 13. Authoring checklist

1. Write `data/book/internal-developer-platform/interview.json` to the schema,
   matching `cicd-pipeline`/`payment-system` depth. Use small targeted edits; the
   file is one big JSON object.
2. Register it in `data/book/index.json` under the existing **`developer-platform`
   ("Developer Platform & CI/CD")** category, after `cicd-pipeline`:
   ```json
   { "id": "internal-developer-platform",
     "name": "Internal Developer Platform (IDP)",
     "path": "data/internal-developer-platform/interview.json" }
   ```
3. Add an `icon.png`.
4. Validate JSON: `python3 -c "import json; json.load(open('.../interview.json'))"`.
5. Cross-check `view.highlight` ids ∈ that view's nodes; `view.links` resolve to
   `highLevelArchitecture.links`; sequence participants are canonical node ids;
   `satisfies[*].steps[*]` slugs resolve to real step ids; `step.probeLinks`
   resolve to `toProbeFurther.links[].id`; `step.patterns`/`patternCatalog`
   references resolve.
6. `python3 build.py` and commit the regenerated `docs/`.
7. Optionally run the asset generators (§12), then `downsize-images.py`.
