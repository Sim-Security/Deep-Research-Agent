# Deep Research Agent - Deployment Guide

Production deployment instructions for GCP Cloud Run.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [GCP Setup](#gcp-setup)
3. [Deployment Methods](#deployment-methods)
4. [Environment Variables](#environment-variables)
5. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
6. [Cost Optimization](#cost-optimization)

---

## Prerequisites

### Local Requirements

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- [Docker](https://docs.docker.com/get-docker/)
- Git

### GCP Requirements

- GCP Project with billing enabled
- APIs enabled:
  - Cloud Run API
  - Cloud Build API
  - Artifact Registry API
  - Secret Manager API

---

## GCP Setup

### 1. Initial Configuration

```bash
# Set project
export PROJECT_ID="your-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

### 2. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

### 3. Create Artifact Registry Repository

```bash
gcloud artifacts repositories create deep-research-agent \
  --repository-format=docker \
  --location=$REGION \
  --description="Deep Research Agent Docker images"
```

### 4. Configure Secrets (Optional but Recommended)

Store API keys securely in Secret Manager:

```bash
# Create secrets
echo -n "your-openrouter-key" | gcloud secrets create openrouter-api-key --data-file=-
echo -n "your-tavily-key" | gcloud secrets create tavily-api-key --data-file=-
echo -n "your-langchain-key" | gcloud secrets create langchain-api-key --data-file=-

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:$PROJECT_ID-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 5. Service Account for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-deployer-key.json \
  --iam-account=github-deployer@$PROJECT_ID.iam.gserviceaccount.com

# Add to GitHub Secrets:
# GCP_PROJECT_ID: your-project-id
# GCP_SA_KEY: contents of github-deployer-key.json
```

---

## Deployment Methods

### Method 1: GitHub Actions (Recommended)

Automatic deployment on push to `main`:

1. Configure GitHub Secrets:
   - `GCP_PROJECT_ID`: Your GCP project ID
   - `GCP_SA_KEY`: Service account JSON key

2. Push to main branch:
   ```bash
   git push origin main
   ```

3. Monitor deployment in GitHub Actions tab.

### Method 2: Cloud Build (Direct)

```bash
# From project root
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=$REGION
```

### Method 3: Manual gcloud Deploy

```bash
# Build locally
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/deep-research-agent/deep-research-agent:latest .

# Push to Artifact Registry
docker push $REGION-docker.pkg.dev/$PROJECT_ID/deep-research-agent/deep-research-agent:latest

# Deploy to Cloud Run
gcloud run deploy deep-research-agent \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/deep-research-agent/deep-research-agent:latest \
  --region=$REGION \
  --platform=managed \
  --port=8080 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300s \
  --allow-unauthenticated
```

### Method 4: Local Development

```bash
# Run with Docker
docker build -t deep-research-agent .
docker run -p 8080:8080 --env-file .env deep-research-agent

# Access at http://localhost:8080
```

---

## Environment Variables

### Required for Production

| Variable | Description | Source |
|----------|-------------|--------|
| `OPENROUTER_API_KEY` | OpenRouter API key | Secret Manager |
| `STREAMLIT_SERVER_PORT` | Server port (8080) | Set in deployment |
| `STREAMLIT_SERVER_HEADLESS` | Headless mode | Set in deployment |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `TAVILY_API_KEY` | Tavily search API | DuckDuckGo fallback |
| `LANGCHAIN_API_KEY` | LangSmith tracing | Disabled |
| `LANGCHAIN_TRACING_V2` | Enable tracing | false |

### Setting Environment Variables

**Via Cloud Run Console:**
1. Go to Cloud Run > Service > Edit
2. Add under "Variables & Secrets"

**Via gcloud:**
```bash
gcloud run services update deep-research-agent \
  --set-env-vars="KEY=value"
```

**Via Secret Manager:**
```bash
gcloud run services update deep-research-agent \
  --set-secrets="OPENROUTER_API_KEY=openrouter-api-key:latest"
```

---

## Monitoring & Troubleshooting

### View Logs

```bash
# Stream logs
gcloud run services logs read deep-research-agent --region=$REGION --tail=50

# View in Cloud Console
# https://console.cloud.google.com/run/detail/$REGION/deep-research-agent/logs
```

### Health Check

The application exposes a health endpoint at `/_stcore/health`:

```bash
SERVICE_URL=$(gcloud run services describe deep-research-agent --region=$REGION --format='value(status.url)')
curl -sf "$SERVICE_URL/_stcore/health"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Container fails to start | Check logs for missing env vars |
| 503 errors | Increase memory/CPU or check cold start |
| Timeout errors | Increase `--timeout` setting |
| Permission denied | Verify Secret Manager IAM bindings |

### Scaling Configuration

```bash
# Adjust scaling parameters
gcloud run services update deep-research-agent \
  --min-instances=1 \      # Keep warm (reduces cold starts, increases cost)
  --max-instances=20 \     # Handle more traffic
  --concurrency=100        # Requests per instance
```

---

## Cost Optimization

### Recommendations

1. **Min Instances = 0**: Only pay when used (default)
2. **Set Concurrency**: Higher values = fewer instances
3. **Right-size Memory**: 2Gi is sufficient for most workloads
4. **CPU Allocation**: Set to "Only during requests" for intermittent use

### Estimated Costs (us-central1)

| Configuration | Monthly Estimate |
|--------------|------------------|
| 0 min instances, light use | $5-20 |
| 1 min instance, moderate use | $50-100 |
| High traffic, autoscaling | $100-500+ |

### Cost Monitoring

```bash
# Set budget alerts
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Deep Research Agent Budget" \
  --budget-amount=100USD
```

---

## Quick Reference

```bash
# Deploy
gcloud builds submit --config cloudbuild.yaml

# View service URL
gcloud run services describe deep-research-agent --format='value(status.url)'

# View logs
gcloud run services logs read deep-research-agent --tail=100

# Rollback to previous revision
gcloud run services update-traffic deep-research-agent --to-revisions=REVISION_NAME=100
```

---

**Questions?** Open an issue on GitHub or check [Cloud Run documentation](https://cloud.google.com/run/docs).
