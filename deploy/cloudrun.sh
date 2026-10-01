#!/usr/bin/env bash
# Deploy Agentic to Google Cloud: Cloud Run + Cloud SQL (Postgres) + Memorystore (Redis),
# with Claude served from Vertex AI so model usage is billed to your GCP account.
#
#   PROJECT_ID=my-project ./deploy/cloudrun.sh
#
# Re-runnable: existing resources are reused.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-agentic}"
SQL_INSTANCE="${SQL_INSTANCE:-agentic-pg}"
REDIS_INSTANCE="${REDIS_INSTANCE:-agentic-redis}"
REPO="${REPO:-agentic}"
SA_NAME="${SA_NAME:-agentic-run}"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:$(git rev-parse --short HEAD)"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com sqladmin.googleapis.com redis.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com \
  aiplatform.googleapis.com vpcaccess.googleapis.com

echo "==> Service account"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name "Agentic Cloud Run"
for role in roles/aiplatform.user roles/cloudsql.client roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SA" --role "$role" --condition=None >/dev/null
done

echo "==> Secrets"
ensure_secret() {  # name, value-generator
  gcloud secrets describe "$1" >/dev/null 2>&1 || \
    eval "$2" | gcloud secrets create "$1" --data-file=- --replication-policy=automatic
}
ensure_secret agentic-db-password "openssl rand -base64 24 | tr -d '/+='"
ensure_secret agentic-ro-password "openssl rand -base64 24 | tr -d '/+='"
ensure_secret agentic-api-keys "openssl rand -hex 24"
DB_PASSWORD="$(gcloud secrets versions access latest --secret agentic-db-password)"
RO_PASSWORD="$(gcloud secrets versions access latest --secret agentic-ro-password)"

echo "==> Cloud SQL (Postgres 16)"
gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1 || \
  gcloud sql instances create "$SQL_INSTANCE" --database-version POSTGRES_16 \
    --tier db-f1-micro --region "$REGION" --storage-auto-increase
gcloud sql databases describe agentic --instance "$SQL_INSTANCE" >/dev/null 2>&1 || \
  gcloud sql databases create agentic --instance "$SQL_INSTANCE"
gcloud sql users create agentic --instance "$SQL_INSTANCE" --password "$DB_PASSWORD" 2>/dev/null || \
  gcloud sql users set-password agentic --instance "$SQL_INSTANCE" --password "$DB_PASSWORD"
CONN_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format 'value(connectionName)')"

echo "==> Memorystore (Redis) + Serverless VPC connector"
gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" >/dev/null 2>&1 || \
  gcloud redis instances create "$REDIS_INSTANCE" --size 1 --region "$REGION" --tier basic
REDIS_HOST="$(gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" --format 'value(host)')"
gcloud compute networks vpc-access connectors describe agentic-conn --region "$REGION" >/dev/null 2>&1 || \
  gcloud compute networks vpc-access connectors create agentic-conn --region "$REGION" \
    --network default --range 10.8.0.0/28

echo "==> Build image with Cloud Build"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION"
gcloud builds submit --tag "$IMAGE" .

echo "==> Deploy Cloud Run"
SOCKET="/cloudsql/${CONN_NAME}"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" --region "$REGION" --service-account "$SA" \
  --add-cloudsql-instances "$CONN_NAME" --vpc-connector agentic-conn \
  --allow-unauthenticated --timeout 600 --concurrency 40 --min-instances 0 --max-instances 5 \
  --memory 1Gi --cpu 1 \
  --set-env-vars "LLM_PROVIDER=vertex,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=global,EFFORT=medium" \
  --set-env-vars "REDIS_URL=redis://${REDIS_HOST}:6379/0" \
  --set-env-vars "DATABASE_URL=postgresql://agentic:${DB_PASSWORD}@/agentic?host=${SOCKET}" \
  --set-env-vars "READONLY_DATABASE_URL=postgresql://agent_readonly:${RO_PASSWORD}@/agentic?host=${SOCKET}" \
  --set-secrets "API_KEYS=agentic-api-keys:latest"

cat <<MSG

Deployed. One-time database seeding (read-only role + analytics demo data):
  cloud-sql-proxy ${CONN_NAME} &
  PGPASSWORD='${DB_PASSWORD}' POSTGRES_USER=agentic POSTGRES_DB=agentic \\
    READONLY_PASSWORD='${RO_PASSWORD}' PGHOST=127.0.0.1 sh db/init/01-analytics.sh

API key for the UI:  gcloud secrets versions access latest --secret agentic-api-keys
Service URL:         $(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
MSG
