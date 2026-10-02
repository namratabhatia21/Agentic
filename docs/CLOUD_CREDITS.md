# Using your cloud credits

Running the chatbot costs model tokens plus servers and a database. Both can be paid
with credits on the platform you deploy to.

The app can call Claude through three platforms. Pick the one where your credits are
by setting `LLM_PROVIDER`. No code changes needed.

## Option A: Google Cloud credits → Vertex AI (+ Cloud Run)

1. In the Google Cloud console, open **Vertex AI → Model Garden**, find Claude Opus 5.5
   and click **Enable**. Accept the terms.
2. Check that your credits apply. Open **Billing → Credits** and read the credit's
   scope. Program credits (Google for Startups, education, research) usually cover
   Vertex AI. Some promotional or free-trial credits exclude partner/Marketplace models.
   If Claude isn't covered, your credits still pay for Cloud Run, Cloud SQL and
   Memorystore, and you can use Option C for the model.
3. Configure:
   ```env
   LLM_PROVIDER=vertex
   GCP_PROJECT_ID=your-project-id
   GCP_REGION=global
   ```
4. Auth:
   - **Cloud Run**: give the service account `roles/aiplatform.user`.
     `deploy/cloudrun.sh` does this.
   - **Local Docker**: run `gcloud auth application-default login`, then
     ```env
     GCLOUD_CONFIG_DIR=~/.config/gcloud
     GOOGLE_APPLICATION_CREDENTIALS=/gcloud/application_default_credentials.json
     ```
5. Deploy: `PROJECT_ID=your-project-id ./deploy/cloudrun.sh`

On Vertex, web search uses the basic variant and web fetch isn't available. All the
other tools work the same.

## Option B: AWS credits → Amazon Bedrock

1. In the Bedrock console, open **Model access** and request access to Anthropic Claude.
2. AWS Activate and most promotional credits apply to Bedrock usage. Check
   **Billing → Credits** for the eligible services list.
3. Configure:
   ```env
   LLM_PROVIDER=bedrock
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=...        # or an IAM role on ECS/EC2 (preferred)
   AWS_SECRET_ACCESS_KEY=...
   ```
   The IAM principal needs `bedrock:InvokeModel` and
   `bedrock:InvokeModelWithResponseStream`.
4. Deploy the same container to ECS Fargate or App Runner, with RDS Postgres and
   ElastiCache Redis.

Bedrock has no server-side web search/fetch tools. The bot still gets live data from
arXiv, Hacker News, Wikipedia, weather and exchange-rate tools.

## Option C: Anthropic Console credits → Claude API

1. Create a key at console.anthropic.com → **API keys**. Prepaid credits under
   **Billing** are spent automatically.
2. Configure:
   ```env
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   This option has every feature: dynamic web search, web fetch, and automatic
   refusal fallback.

## Option D: Hugging Face credits → open-weight models

1. Create a token at huggingface.co/settings/tokens. Fine-grained, with
   **Make calls to Inference Providers** enabled.
2. Free accounts get a small monthly inference allowance, and HF PRO includes more.
   After that, usage is billed by Hugging Face at the provider's rates, or to your
   own provider keys if you add them in HF settings.
3. Configure:
   ```env
   LLM_PROVIDER=huggingface
   HF_TOKEN=hf_...
   HF_CHAT_MODEL=Qwen/Qwen3-235B-A22B-Instruct-2507   # any model with tool calling
   ```
   Browse models that support tool use at huggingface.co/models?inference_provider=all.

The same `HF_TOKEN` also turns on the image-generation and classification tools with
any provider. Semantic search needs no credits: the `embeddings` service runs the
Hugging Face model locally on CPU.

On Cloud Run you can skip the TEI service: leave `EMBEDDINGS_URL` empty, set `HF_TOKEN`,
and embeddings are computed by Hugging Face instead. You can also deploy the TEI image as
a second Cloud Run service and point `EMBEDDINGS_URL` at it.

## Keeping the bill low

- `EFFORT=low` or `medium` (the default) costs much less than `high`/`xhigh` for
  chat-style traffic. Raise it only if answers on hard questions aren't good enough.
- Prompt caching is already on. Watch `agentic_tokens_total{kind="cache_read_input_tokens"}`:
  cached input tokens cost about 10% of normal input.
- Set `RATE_LIMIT_PER_MINUTE` and `API_KEYS` so strangers can't spend your credits.
- Set a budget alert: GCP **Billing → Budgets & alerts**, AWS **Budgets**, or the
  Anthropic Console spend limits.
- On GCP, Cloud Run scales to zero. Cloud SQL and Memorystore don't, and they are
  the main fixed costs. The smallest tiers are enough for a demo.
