# Portfolio plan: "I built every layer under an LLM agent"

> Written without access to the CV. Adjust the "why it matters" lines to match your
> real experience before publishing.

## The story (one paragraph for your README / LinkedIn)

Most people call an LLM API. I built the layers underneath it and then made them
trustworthy: a small **LLM from scratch** (how generation works), a **reranker from
scratch** (how retrieval quality is decided), an **explainability toolkit** built on
LIME that shows *why* the reranker ranked a document where it did, and a
**cloud reference architecture** that runs it all in production. The existing
[Agentic](../README.md) chatbot is the capstone that wires them together.

```
          ┌────────────── Agentic (capstone, already built) ──────────────┐
 query ─► │ agent ─► hybrid search (pgvector + keyword) ─► RERANKER ─► LLM │ ─► cited answer
          └────────────────────────────┬──────────────────┬───────────────┘
                                       │                  │
                       repo 2: reranker-from-scratch   repo 1: mini-llm (swap-in generator)
                                       │
                       repo 3: explain-rank (LIME) ─► "Why this source?" in the UI
                                       │
                       repo 4: cloud-reference-architecture (Terraform, GCP primary)
```

Each repo stands alone (own README, results table, blog post) **and** plugs into the
capstone. That is the story: depth in each layer, plus integration.

## Repo 1: `mini-llm` (weeks 1-3)

**Goal:** a decoder-only transformer trained end to end by you.

| Step | What you build | Done when |
|---|---|---|
| 1 | Byte-level BPE tokenizer (own implementation, tested against `tiktoken`) | Round-trips any text |
| 2 | Attention → multi-head → transformer block (RMSNorm, RoPE, SwiGLU, pre-norm) in plain PyTorch | Overfits one batch to ~0 loss |
| 3 | Training loop: AdamW, cosine LR, warmup, grad clipping, bf16, checkpointing, resume | Loss curve is smooth |
| 4 | Train 10-30M params on TinyStories (laptop/Colab GPU, a few hours) | Generates coherent short stories |
| 5 | Inference: temperature / top-k / top-p, **KV cache**, benchmark with vs. without | Report tokens/s speedup |
| 6 | Stretch: small SFT on instruction data, or LoRA from scratch | Follows simple instructions |

**Deliverables:** loss curves, perplexity table, a sampling demo, a 1-page "what I
learned" (e.g. why the KV cache matters, effect of RoPE vs. learned positions).
**Learn from:** Karpathy "Let's build GPT" / nanoGPT, Raschka *Build a LLM From
Scratch*, Stanford CS336. Write your own code; use these only to check yourself.

## Repo 2: `rerank-from-scratch` (weeks 4-6)

**Goal:** a cross-encoder reranker you train and evaluate against real baselines.

1. **Data:** MS MARCO passages (training), BEIR subsets such as SciFact, FiQA, NFCorpus (zero-shot test).
2. **Baselines first:** BM25 and a bi-encoder (`bge-small` or similar). Record nDCG@10, MRR@10, Recall@100.
3. **Your bi-encoder:** in-batch-negatives contrastive loss (InfoNCE), then **hard-negative mining** with BM25.
4. **Your cross-encoder:** small transformer (reuse the Repo 1 blocks or fine-tune MiniLM), pairwise/listwise loss (RankNet or LambdaRank).
5. **Distillation:** distil a large reranker (`bge-reranker`) into your small one; report quality vs. latency.
6. **Evaluate honestly:** table with BM25 / bi-encoder / yours / bge-reranker, plus p50/p95 latency and cost per 1k queries.
7. **Integrate:** add a `rerank` stage to Agentic's `knowledge` tool (`app/tools/knowledge.py`), after the existing hybrid search. Show before/after on a fixed question set.

**Why it matters:** retrieval quality is where most RAG systems fail, and
you can measure it. Include an ablation (with/without hard negatives, distillation).

## Repo 3: `explain-rank` (weeks 7-9): explainability on LIME

**Goal:** explain *ranking*, not just classification. This is the original contribution.

1. **LIME for a reranker:** the "model" is `f(query, doc) → score`. Perturb tokens
   or sentences in the document (and optionally the query), fit a locally weighted
   linear surrogate on the score change, and return the top contributing spans.
2. **Pairwise explanations:** "why did A outrank B?" by explaining the score
   *difference*. This is more useful than explaining one score.
3. **Compare against alternatives:** leave-one-out, SHAP (Partition explainer),
   Integrated Gradients, attention rollout.
4. **Measure faithfulness, not just pretty highlights:**
   - Comprehensiveness / sufficiency, deletion and insertion AUC
   - **Stability:** rerun LIME with different seeds, report rank correlation of attributions
   - Runtime per explanation
5. **Address known LIME weaknesses** (pick one as your experiment): off-distribution
   perturbations (use sentence-level or mask-token perturbations instead of
   deletion), instability (more samples vs. kernel width tuning), correlated tokens.
6. **Surface it:** a "Why this source?" button in the Agentic UI that highlights the
   spans driving the rerank score; also a CLI and a small notebook.
7. **Extend to RAG answers (stretch):** attribute generated answer sentences to
   retrieved chunks and check against the citations the agent produced.

**Deliverables:** a pip-installable package, a faithfulness benchmark table, and a
short write-up on when LIME is and isn't trustworthy. That write-up is your
strongest portfolio artifact.

> **Update:** Repo 4 is now the Cloud Architecture Advisor (AWS first, then GCP, Azure
> and OSS). The full product plan is in [CLOUD_ADVISOR_PLAN.md](CLOUD_ADVISOR_PLAN.md).
> The section below is the earlier static reference-architecture idea, kept for context.

## Repo 4: `genai-cloud-reference-architecture` (weeks 10-12)

**Goal:** a researched, deployable reference architecture, not a diagram only.

**Recommendation: GCP as primary** because Agentic already deploys to Cloud Run and
uses Vertex AI. Document AWS and Azure equivalents in the same repo so it reads as
cloud-aware, not cloud-locked. Terraform for the primary, a mapping table for the others.

| Concern | GCP (primary) | AWS | Azure |
|---|---|---|---|
| App compute | Cloud Run | ECS Fargate (or App Runner) | Container Apps |
| LLM access | Vertex AI (Gemini, Claude, open models) | Bedrock | Azure AI Foundry / Azure OpenAI |
| Vector + relational store | Cloud SQL or AlloyDB for PostgreSQL + pgvector | Aurora PostgreSQL + pgvector | Azure Database for PostgreSQL + pgvector |
| Managed search / vector (alt.) | Vertex AI Vector Search | OpenSearch Serverless | Azure AI Search |
| Cache / rate limits | Memorystore (Redis) | ElastiCache | Azure Cache for Redis |
| Model serving (your reranker) | Vertex AI endpoints or Cloud Run GPU | SageMaker endpoint | Azure ML online endpoint |
| Async / ingestion | Pub/Sub + Cloud Run jobs | SQS + Lambda / Fargate tasks | Service Bus + Container Apps jobs |
| Object storage / data lake | Cloud Storage + BigQuery | S3 + Athena | Blob Storage + Synapse / Fabric |
| Secrets | Secret Manager | Secrets Manager | Key Vault |
| Images / CI/CD | Artifact Registry + Cloud Build / GitHub Actions (Workload Identity Federation) | ECR + CodeBuild / GitHub Actions (OIDC) | ACR + GitHub Actions (OIDC) |
| Identity | IAM service accounts, IAP | IAM roles, Cognito | Entra ID, managed identities |
| Edge / protection | Cloud Load Balancing + Cloud Armor | CloudFront + WAF | Front Door + WAF |
| Network isolation | VPC, Private Service Connect, VPC-SC | VPC, PrivateLink | VNet, Private Endpoints |
| Observability | Cloud Logging / Monitoring / Trace | CloudWatch + X-Ray | Azure Monitor + App Insights |
| Guardrails | Model Armor, Vertex safety filters | Bedrock Guardrails | Azure AI Content Safety |

**What to include in the repo (this is what makes it "researched"):**
- `docs/decisions/` ADRs: why Cloud Run vs. GKE, pgvector vs. managed vector DB, managed LLM vs. self-hosted
- Diagrams: request path, ingestion path, eval/feedback loop, trust boundaries
- Terraform modules: network, Cloud Run service, Cloud SQL, secrets, IAM least-privilege, monitoring alerts
- Cost model: monthly estimate at 3 traffic levels, with the biggest cost drivers (tokens, GPU, DB)
- Security: private networking, no static keys (workload identity), prompt-injection and PII controls, audit logs
- Reliability: SLOs, autoscaling, timeouts and retries, fallback model (the repo already switches providers)
- Evaluation in CI: retrieval metrics + LLM-judge regression set on every PR
- **Research basis:** cite and map your design to the Google Cloud Architecture Center
  (generative AI / RAG reference architectures), the AWS Well-Architected
  Generative AI Lens and Prescriptive Guidance, and the Azure Architecture Center
  (RAG and baseline OpenAI chat architectures). Verify the current versions of
  these documents when you write it.

## Capstone: Agentic (already built, weeks 13-14)

Wire it together and publish:
1. Swap in your reranker (Repo 2) and the "Why this source?" explainer (Repo 3).
2. Optional: serve `mini-llm` as a selectable provider to show the full path (toy quality, real plumbing).
3. Deploy with Repo 4's Terraform, then put the live demo link and a 2-minute Loom video at the top of every README.

## Timeline

| Weeks | Work | Public output |
|---|---|---|
| 1-3 | `mini-llm` | Repo + blog post "Training a 20M LLM on one GPU" |
| 4-6 | `rerank-from-scratch` | Repo + results table + post "Reranker vs. BM25: what the numbers say" |
| 7-9 | `explain-rank` | Package + faithfulness benchmark + post "When can you trust LIME on rankers?" |
| 10-12 | Cloud reference architecture | Repo + diagrams + ADRs + cost model |
| 13-14 | Integrate into Agentic, deploy, polish | Live demo + video + portfolio page |

Rules that keep this credible: every repo has a results table with baselines, a
"what didn't work" section, reproducible commands (`make train`, `make eval`), and
tests for the core math. Publish as you go, not at the end.
