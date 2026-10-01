# Cloud Architecture Advisor: product and build plan

Working name: `cloud-architecture-advisor` (a standalone repo; this file lives here only
until that repo exists). Start with AWS, then add GCP, Azure and open-source options.

> Research was done on 2026-10-01 through web search. Items marked **(verified)** were
> confirmed from a source page. Items marked **(unverified)** come from search snippets
> or memory and must be checked before you rely on them. The official AWS icon terms
> page could not be fetched in this session, so read it yourself first.

---

## 1. The problem

Someone has an idea ("a photo-sharing app for 50k users", "a RAG chatbot over our PDFs")
and needs to answer four questions before writing code:

1. **What should I build it with?** (which services, and why)
2. **What will it cost?** (monthly, yearly, at different traffic levels)
3. **How do I pay less?** (commitments, Spot, tiering, right-sizing)
4. **Which cloud, or open source, is better for me?**

Today, answering these means juggling a diagram tool, a pricing calculator, three
vendors' documentation, and a lot of guesswork. Each step is separate, and none of them
explains *why*. The result is slow decisions and bills that surprise people.

### Who it's for (pick a primary one)

| User | Pain | What they need from the tool |
|---|---|---|
| **Learners and students** (your audience as an educator) | Can't tell why one service was chosen over another | Architecture with a rationale per service, shown at "teach mode" depth |
| **Startup founders and solo developers** | No architect on staff; fear of a surprise bill | A sane starting design, cost range, and cheap options |
| **Consultants and pre-sales engineers** | Hours spent on sizing and diagrams for proposals | Fast first draft with assumptions they can edit and export |

**Recommended primary user: learners and early-stage builders.** It fits your background,
and it is where "explains why" matters more than raw speed.

---

## 2. What already exists

| Tool | What it does | Source |
|---|---|---|
| **AWS Pricing Calculator** + **BCM Pricing Calculator API** | Official estimates. The API creates workload estimates programmatically and can model Savings Plans and Reserved Instances. Free. | AWS docs **(verified from search results)** |
| **AWS Price List API** | Public list prices per service and region | AWS docs **(unverified, from memory)** |
| **awslabs `aws-pricing-mcp-server`** | Lets an AI client query AWS prices | awslabs docs **(verified)** |
| **awslabs `aws-diagram-mcp-server`** | Generates diagrams from Python code. **Deprecated**; replaced by the diagram skill in the `deploy-on-aws` plugin. | PyPI page **(verified)** |
| **OpenArchFlow** (MIT, open source) | Natural language → interactive AWS diagram, with AWS Pricing API cost estimates, Terraform export, and a local emulator | GitHub / project site **(verified from search results)** |
| **ArchGenie** | Natural language → diagram across **AWS, Azure and GCP**, plus per-resource cost (reserved/spot/on-demand), IaC, and security grades | Vendor site **(from search snippets; blog page couldn't be fetched)** |
| **Visual Paradigm AI Cloud Architecture Studio** | AI diagrams with strategy presets (low cost, high availability) | Vendor site **(from search snippets)** |
| **Cloudcraft** | Diagrams of **existing** infrastructure (live scan) with cost estimates; AWS, Azure, GCP; paid | Vendor site **(from search snippets)** |
| **Brainboard** | Visual design to Terraform with CI/CD; multi-cloud; paid | Vendor site **(from search snippets)** |
| **Infracost** | Cost estimates for **Infrastructure-as-Code** (Terraform) and a Cloud Pricing API | Vendor docs **(from search snippets)** |
| **Azure Retail Prices API** | Public list prices, **no authentication needed** | Microsoft docs **(verified)** |
| **Google Cloud Billing Catalog API** | Public list prices, **needs an API key** | Google docs **(verified)** |
| Blog and comparison pages (Rackspace, Veritis, others) | Manual AWS vs Azure vs GCP price comparisons | Web **(verified they exist)** |

**Conclusion: this space is crowded.** "Type an idea, get an AWS diagram and a cost" is
already done, including by a free open-source project and by a multi-cloud commercial
one. Building only that would be a tutorial-level repeat.

### Gaps worth targeting

These are hypotheses based on what I found. In my searches I did not see a tool that
does them well. **Validate by trying ArchGenie and OpenArchFlow with 10 of your own test
ideas** before committing.

1. **Fair like-for-like comparison.** Tools generate a design per cloud. Comparing means
   pricing the *same capabilities and sizing* on each, and showing where services are
   *not* equivalent.
2. **Explanations at the service level.** "Why S3 and not EFS, and what would change my
   mind?" This is aimed at learners, not just output.
3. **Trustworthy numbers.** Published error against the official calculators, an
   explicit assumptions list, the pricing date, and sensitivity ("what if traffic
   doubles?"). Most tools show a single confident number.
4. **Commitment advice with break-even analysis.** Not just "Savings Plans save ~30%" but
   "at your expected utilisation, a 1-year no-upfront plan breaks even at month N, and
   you lose money if usage drops below X%".
5. **Honest open-source option.** Self-hosting includes engineer time and operations,
   not just VM price.

### Positioning statement

> An explainable architecture advisor that turns an idea into a cloud-neutral design,
> then shows a transparent, validated cost and commitment comparison across AWS, GCP,
> Azure and open-source options, with a reason for every choice.

### Non-goals (for v1)

- Not an IaC generator or deployer (Terraform export is a later bonus).
- Not a live-account scanner (Cloudcraft does that).
- Not 200 services. About 15 capabilities and 5 patterns, done well.

---

## 3. Product description

**Journey**

1. User describes the idea in a sentence or two.
2. The tool asks 3-6 clarifying questions (users, traffic, data size, availability,
   compliance, region, budget, team skills), with sensible defaults.
3. It shows a **cloud-neutral architecture**, then provider tabs: **AWS | GCP | Azure |
   OSS**, each with a diagram, a cost table and a rationale for each service.
4. It shows **cost at low, expected and high usage**, monthly and yearly, with a line
   item per service and the hidden costs (data transfer, NAT, logs, KMS).
5. It shows **savings**: commitment options with break-even, Spot where safe, tiering,
   Graviton or equivalent, free tier effects.
6. It shows **recommended additions**: security, backup, monitoring, DR, budgets, each
   with its cost, plus a Well-Architected style checklist.
7. One-page report (PDF/Markdown) with the diagram, assumptions and pricing date.

**Teach mode (differentiator).** A toggle that expands each decision: alternatives
considered, trade-offs, what a Solutions Architect would ask, and a link to the official
docs. Aligned to common AWS certification topics.

---

## 4. System design

```
 idea ─► Intake (LLM) ─► Requirements JSON
                              │
                              ▼
        Pattern selector + Architect (LLM constrained by pattern library)
                              │
                              ▼
        NEUTRAL SPEC (capabilities + sizing + edges + rationale)
                              │
        ┌──────────┬──────────┼───────────┐
        ▼          ▼          ▼           ▼
   AWS mapper  GCP mapper  Azure mapper  OSS mapper     (mapping tables, not LLM)
        │          │          │           │
        ▼          ▼          ▼           ▼
   Usage model ─► Pricing adapters ─► PriceLine[] ─► Cost + commitment engine
        │
        ▼
   Diagram renderer (icons)      Advisor (rules + LLM explanations)      Report
```

### 4.1 Principles

- **The LLM proposes, code calculates.** The model never produces a price. It produces
  structured data that code validates and prices.
- **Everything is data.** Patterns, mappings and rules are versioned YAML/JSON that you
  review, so quality is under your control and diffs are readable.
- **Every number is traceable** to a price SKU, a usage assumption, and a pricing date.

### 4.2 Neutral spec (first concrete deliverable)

```yaml
requirements:
  users: 50000
  peak_rps: 40
  data_gb: 500
  data_growth_gb_per_month: 50
  availability_target: "99.9"
  region: "india-mumbai"        # mapped to ap-south-1 / asia-south1 / centralindia
  compliance: []
  monthly_budget_usd: 300
components:
  - id: web
    capability: container-service   # neutral
    sizing: { vcpu: 2, memory_gb: 4, instances: 2 }
    rationale: "Steady traffic and long-lived connections favour containers over functions."
  - id: db
    capability: relational-db
    sizing: { engine: postgres, storage_gb: 200, multi_az: true }
  - id: media
    capability: object-storage
    sizing: { gb: 500, requests_per_month: 20000000, egress_gb: 800 }
  - id: cdn
    capability: cdn
edges:
  - { from: cdn, to: web }
  - { from: web, to: db }
  - { from: web, to: media }
```

Mapping table entry (per capability, per provider), including **fidelity notes**:

```yaml
object-storage:
  aws:   { service: "Amazon S3",       fidelity: exact }
  gcp:   { service: "Cloud Storage",   fidelity: exact }
  azure: { service: "Blob Storage",    fidelity: exact }
  oss:   { service: "MinIO on VMs",    fidelity: partial,
           note: "You operate durability, upgrades and scaling." }
```

### 4.3 Pricing adapters

One adapter per cloud, all returning a common `PriceLine`
(`sku, unit, unit_price, region, currency, effective_date, source_url`).

| Cloud | Source | Notes |
|---|---|---|
| AWS | Price List API / bulk files; validate against the BCM Pricing Calculator API | Cache per region; the files are large |
| Azure | Retail Prices API (open) | Filter by service and region |
| GCP | Cloud Billing Catalog API (**API key required**) | Store the key as a secret |
| OSS | VM or Kubernetes node price from the cloud adapters, plus an **ops-effort assumption** (hours per month, hourly rate) | Editable defaults |

### 4.4 Cost model

- **Usage model** per capability (requests, GB stored, GB transferred, hours). Ranges
  for low / expected / high, not one number.
- **Line items** for hidden costs: data transfer (internet, cross-AZ, cross-region), NAT
  gateways, load balancers, logs and metrics, KMS, public IPv4 addresses, support plan.
- **Free tier** handled as a toggle (new accounts only).
- **Commitment engine** (per cloud's own rules; do not force a shared abstraction):
  - AWS: Compute Savings Plans, EC2 Instance Savings Plans, Reserved Instances (RDS,
    ElastiCache, etc.), 1y/3y, no / partial / all upfront.
  - GCP: committed use discounts. Azure: Reservations, Savings Plans, Hybrid Benefit.
    **(unverified: rules must be confirmed per service when you implement)**
  - **Break-even:** with discount `d`, a commitment pays off only if the committed
    capacity is used at least `(1 - d)` of the time. For a 30% discount that is 70%
    utilisation. Show the month where cumulative savings turn positive and the
    downside if usage falls.
- **Sensitivity:** tornado chart of the top five cost drivers (e.g. egress, DB size,
  traffic).
- Always display currency, region, pricing date and "list price, not your negotiated rate".

### 4.5 Advisor

Deterministic rules first, LLM only to phrase explanations:
- Well-Architected checks (security, reliability, cost, performance, operational
  excellence, sustainability) per pattern.
- Rule examples: single-AZ database with a 99.9% target → flag; public S3 with no CDN
  and high egress → suggest CDN; NAT gateway cost above a threshold → suggest VPC
  endpoints.
- Each add-on lists its cost impact and the risk it removes.

### 4.6 Diagram renderer

- Layout is **deterministic** from the spec (VPC > AZ > subnet grouping, left-to-right
  flow); the LLM never places pixels.
- Output SVG and an editable draw.io file. Option: Python `diagrams` library.
- Pluggable icon sets per provider.
- **Icon licensing:** AWS says its architecture icons may be used to build architecture
  diagrams, but they must not be modified or used for non-AWS purposes **(from search
  results; official page not fetched)**. Read the current terms, keep icons unaltered,
  add a "not affiliated with AWS/Google/Microsoft" notice, and check GCP and Azure icon
  terms separately.

### 4.7 LLM guardrails

- Structured outputs validated by Pydantic; reject and retry on schema errors.
- The architect step may only choose from the pattern library and the capability list.
- Prompt-injection hygiene: user text is data, never instructions to tools.
- Log every request with its spec so failures become evaluation cases.

### 4.8 Tech stack (dogfooding AWS, though the app is cloud-neutral)

Python 3.12, FastAPI, Pydantic, Amazon Bedrock for the LLM (model swappable), Postgres
(price cache, saved designs), React front end with tabs, `diagrams` or custom SVG
renderer, scheduled price ingestion job, Terraform for deployment. Tests with pytest and
golden-file diagram tests.

---

## 5. Evaluation (this is what makes it credible)

| What | How | Target |
|---|---|---|
| **Cost accuracy** | 20 reference architectures priced by your tool vs. the official AWS Pricing Calculator (use the BCM API for AWS; manual for GCP/Azure) | Median error under 5%, worst case under 15%, with differences explained |
| **Architecture quality** | You score 20 generated designs on a rubric (fit to requirements, security, reliability, cost sense, over-engineering) | At least 80% rated "acceptable or better" |
| **Schema reliability** | % of runs producing a valid spec on first try | Above 95% |
| **Mapping fairness** | A reviewer per cloud checks every mapping and fidelity note | All "exact" mappings confirmed |
| **Savings advice** | Break-even maths unit-tested against hand-calculated cases | 100% of cases pass |
| **User test** | 5 learners or founders use it; measure time to a decision and trust | Report honestly |
| **Baseline comparison** | Run the same 10 ideas through OpenArchFlow and ArchGenie | Document where yours is better and worse |

Publish the results table, including the failures.

---

## 6. Roadmap with exit criteria

| Phase | Weeks | Build | Exit criterion |
|---|---|---|---|
| 0. Validate | 1 | Try existing tools with 10 ideas; write up gaps; confirm icon terms; choose primary user | Gap list you believe; decision recorded |
| 1. Spec + AWS renderer | 2-3 | Neutral spec schema, 5 patterns, AWS mapping, icon renderer, CLI | 5 specs render clean diagrams, golden tests pass |
| 2. AWS cost engine | 4-5 | Price ingestion, usage model, hidden costs, ranges | Median error under 5% on 10 architectures |
| 3. Commitments + advisor | 6-7 | Savings Plans/RI/Spot, break-even, rules, add-ons, report | Break-even tests pass; advisor flags on seeded bad designs |
| 4. LLM intake + architect | 8-9 | Clarifying questions, pattern selection, rationales, teach mode | 95% valid specs; quality rubric at target |
| 5. Web UI + deploy | 10 | Tabs UI (AWS only), saved designs, Terraform deploy | Live demo URL |
| 6. GCP tab | 11-12 | Mapping, Catalog adapter, icons, commitment rules | Same accuracy target against Google's calculator |
| 7. Azure tab | 13-14 | Same | Same |
| 8. Comparison view | 15 | Side-by-side cost, fidelity warnings, "what differs" | Reviewed by someone who knows GCP and Azure |
| 9. OSS options | ongoing | One at a time (PostgreSQL, MinIO, Kafka, Kubernetes) with ops-effort model | Each has a documented cost model |

Do not start Phase 6 until Phases 1-5 are solid. The neutral spec is the part that is
expensive to change later.

---

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Crowded market | Looks like a copy | Lead with the gaps in section 2; publish the baseline comparison |
| Cost estimates wrong because of usage guesses | Loses trust | Ranges, explicit assumptions, sensitivity, evaluation against calculators |
| Pricing APIs change or are huge | Breakage, slow | Cache with dates, nightly ingest, schema tests |
| GCP and Azure knowledge gap | Wrong mappings | Reviewers, fidelity notes, public known-issues list |
| Icon or trademark misuse | Takedown | Unaltered icons, disclaimers, per-provider terms check |
| LLM produces poor designs | Bad advice | Pattern library, rules, rubric evaluation, "review by an architect" disclaimer |
| Scope creep | Never ships | Fixed v1 list: 5 patterns, about 15 capabilities |
| Public GCP API needs a key | Setup friction | Secret management; mention in README |

---

## 8. Portfolio story

"I'm an AWS educator. Existing AI tools draw diagrams but give a single confident cost
and little explanation. I built an advisor that explains every choice, prices the same
design across clouds fairly, and publishes how accurate it is against the official
calculators." The evaluation table and the baseline comparison are the proof.

## 9. Decisions you need to make

1. Primary user: learners, founders, or consultants? (Recommended: learners and founders.)
2. Is "explain every choice" (teach mode) your headline differentiator?
3. Which 5 patterns first? (Suggested: serverless web app, containerised API, static
   site + API, data pipeline, RAG/GenAI app.)
4. Who can review GCP and Azure mappings?
