# AWS Deployment — AI_GOVERNANCE

Production target: **ECS Fargate + RDS PostgreSQL + Application Load Balancer + ECR + Secrets Manager**.

This extends the existing Docker images — no application rewrite.

## Architecture

```
Internet
   │
   ▼
ALB :80  (→ :443 redirect when HTTPS enabled)
ALB :443 (optional ACM)  ← optional WAFv2
   ├── /api/*, /docs, /redoc, /openapi.json  → ECS backend :8000
   └── /*                                    → ECS frontend :3000
          │
          ├── private subnets (tasks)
          └── RDS Postgres 16 (private, optional Multi-AZ)
```

### Why this approach (vs alternatives)

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **ECS Fargate + RDS + ALB** | Reuses Dockerfiles; scales; private DB; enterprise IAM/secrets | More setup than App Runner | **Recommended** |
| App Runner | Very simple | Weaker networking/RBAC story; dual services awkward | OK for demos |
| EKS | Max flexibility | Ops heavy for current monolith | Later if microservices |

## Prerequisites

- AWS account + IAM user/role with VPC/ECS/RDS/ECR/Secrets rights
- [Terraform](https://www.terraform.io/) >= 1.5
- AWS CLI v2 configured (`aws configure`)
- Docker (for image build/push)

## Deploy steps

### 1. Configure variables

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set jwt_secret_key and provider API keys
```

Cost tip: set `enable_nat_gateway = false` for a cheaper first deploy (tasks get public IPs).

### Enable HTTPS (optional)

In `terraform.tfvars`:

```hcl
domain_name    = "app.example.com"
hosted_zone_id = "Z0123456789ABCDEFG"  # Route53 public zone for example.com
```

Or use an existing ACM certificate in the **same region** as the ALB:

```hcl
domain_name         = "app.example.com"
acm_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."
hosted_zone_id      = "Z0123456789ABCDEFG"  # still recommended for alias A record
```

Terraform will:

1. Issue/validate an ACM cert (DNS via Route53 when creating a new cert)
2. Attach an HTTPS listener on `:443` (TLS 1.2/1.3 policy)
3. Redirect HTTP `:80` → HTTPS
4. Create a Route53 alias `A` record to the ALB when `hosted_zone_id` is set

Then rebuild/push the frontend so `NEXT_PUBLIC_API_BASE_URL` uses the `https://` `api_base_url` output.

### Enable Multi-AZ RDS (optional)

In `terraform.tfvars`:

```hcl
db_multi_az                = true
db_backup_retention_days   = 7   # optional override (prod default is already 7)
db_deletion_protection     = true
```

Effects:

- Synchronous standby in a second AZ; automatic failover on primary failure
- Roughly **2×** RDS instance cost
- Enabling on an **existing** single-AZ instance causes a short maintenance/outage window

Leave `db_multi_az = false` for cheaper first deploys / demos.

### Enable WAF on ALB (optional)

In `terraform.tfvars`:

```hcl
enable_waf     = true
waf_rate_limit = 2000  # requests per IP per 5 minutes
```

Attaches a regional WAFv2 Web ACL to the ALB with:

- Per-IP rate limiting
- AWS Managed Common Rule Set (body size rule counted, not blocked — LLM payloads)
- Known Bad Inputs + SQLi managed groups

CloudWatch metrics / sampled requests are enabled for tuning false positives.

### Enable remote Terraform state (recommended for teams / CI)

State must live outside the main stack (chicken-and-egg). Use the bootstrap root once:

```bash
cd infra/aws/bootstrap
terraform init
terraform apply
terraform output backend_hcl_snippet
```

Then migrate the main stack:

```bash
cd infra/aws
cp backend.hcl.example backend.hcl
# Paste bucket / dynamodb_table / region from bootstrap outputs into backend.hcl

# Uncomment the backend "s3" { } block in versions.tf
terraform init -migrate-state -backend-config=backend.hcl
```

What you get:

- S3 bucket with versioning, AES256 encryption, public access blocked, TLS-only policy
- DynamoDB lock table (`LockID`) for safe concurrent applies
- `backend.hcl` gitignored — do not commit account-specific names

Bootstrap keeps **local** state on purpose (tiny footprint). Protect that state file or re-import the bucket/table if lost.

### 2. Provision infrastructure

```bash
terraform init
terraform plan
terraform apply
```

Note outputs: `app_url`, `api_base_url`, ECR repos, ECS service names.

### 3. Push images and roll ECS

From repo root (Git Bash / WSL / macOS/Linux):

```bash
chmod +x scripts/aws-push-and-deploy.sh
./scripts/aws-push-and-deploy.sh
```

Windows PowerShell equivalent (manual):

```powershell
cd infra\aws
$REGION = terraform output -raw aws_region
$ACCOUNT = terraform output -raw aws_account_id
$API = terraform output -raw api_base_url
$BE = terraform output -raw ecr_backend_repository_url
$FE = terraform output -raw ecr_frontend_repository_url

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
docker build -t "${BE}:latest" ..\..\backend
docker push "${BE}:latest"
docker build --build-arg "NEXT_PUBLIC_API_BASE_URL=$API" -t "${FE}:latest" ..\..\frontend
docker push "${FE}:latest"

aws ecs update-service --cluster (terraform output -raw ecs_cluster_name) --service (terraform output -raw ecs_backend_service_name) --force-new-deployment
aws ecs update-service --cluster (terraform output -raw ecs_cluster_name) --service (terraform output -raw ecs_frontend_service_name) --force-new-deployment
```

### 4. Verify

```bash
terraform output app_url
curl "$(terraform output -raw api_base_url)/health"
```

Open the app URL → sign in → exercise RAG/Agents as locally.

### 5. CI/CD

Workflow: `.github/workflows/deploy-aws.yml` (manual `workflow_dispatch`).

#### Recommended: GitHub OIDC (no long-lived keys)

In `terraform.tfvars`:

```hcl
enable_github_oidc          = true
github_repository           = "your-org/AI_Governance"
create_github_oidc_provider = true   # false if the account already has this provider
# github_oidc_subject_patterns = ["ref:refs/heads/main"]  # tighten later
```

```bash
terraform apply
terraform output -raw github_deploy_role_arn
```

GitHub repo **Variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Value |
|----------|--------|
| `AWS_DEPLOY_ROLE_ARN` | `terraform output github_deploy_role_arn` |
| `AWS_REGION` | e.g. `us-east-1` |

Still required as **Secrets** (non-AWS credentials):

- `ECR_BACKEND_REPO` / `ECR_FRONTEND_REPO`
- `ECS_CLUSTER` / `ECS_BACKEND_SERVICE` / `ECS_FRONTEND_SERVICE`
- `NEXT_PUBLIC_API_BASE_URL`

Remove `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` once OIDC works.

#### Legacy: access keys

If `AWS_DEPLOY_ROLE_ARN` is unset, the workflow falls back to:

- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION`

### Restrict ALB ingress CIDRs (optional)

Default ALB SG allows `0.0.0.0/0` on :80/:443. For staging or private demos, allowlist office/VPN ranges:

```hcl
alb_ingress_cidr_blocks = [
  "203.0.113.0/24",   # office
  "198.51.100.10/32", # bastion / home
]
# alb_ingress_ipv6_cidr_blocks = ["2001:db8::/32"]
```

ECS and RDS stay private (ALB SG → ECS only). Do not lock yourself out: keep a CIDR you can reach from when applying.

### Enable CloudWatch alarms (optional)

```hcl
enable_cloudwatch_alarms = true
alarm_notification_email = "ops@example.com"
```

Creates an SNS topic and alarms for:

| Alarm | Signal |
|-------|--------|
| ALB 5xx | `HTTPCode_Target_5XX_Count` |
| ALB unhealthy hosts | Backend + frontend target groups |
| ECS CPU | Backend + frontend services |
| RDS free storage | Below `alarm_rds_free_storage_bytes` (default 2 GiB) |
| RDS CPU | Above `alarm_rds_cpu_threshold` |

After apply, **confirm the SNS email** in your inbox or notifications stay pending.

### Enable AWS Budgets (optional)

```hcl
enable_aws_budget         = true
monthly_budget_usd        = 100
budget_notification_email = "ops@example.com"  # or reuse alarm_notification_email
```

Creates an account-level monthly COST budget with alerts at:

- **80%** actual spend
- **100%** actual spend
- **100%** forecasted spend

SNS topic allows `budgets.amazonaws.com` to publish. Confirm the email subscription after apply.

> Note: this budget covers the **AWS account** cost, not only this stack. Use a dedicated account/OU for clean isolation.

## Security notes

- RDS is private; only ECS SG can connect; storage encrypted; CloudWatch Postgres logs exported
- Multi-AZ: set `db_multi_az = true` for standby failover (recommended prod)
- Secrets live in Secrets Manager (not baked into images)
- JWT and provider keys never committed
- HTTPS: set `domain_name` + `hosted_zone_id` (or `acm_certificate_arn`) — HTTP redirects to HTTPS
- WAF: set `enable_waf = true` for managed rules + rate limit on the ALB
- Remote state: `infra/aws/bootstrap` → S3 + DynamoDB lock; migrate via `backend.hcl`
- Deploy: GitHub Actions OIDC (`enable_github_oidc`) preferred over static access keys
- ALB ingress: set `alb_ingress_cidr_blocks` to office/VPN CIDRs (default remains `0.0.0.0/0`)
- Observability: `enable_cloudwatch_alarms` + SNS email for ALB/ECS/RDS signals
- Cost: `enable_aws_budget` monthly USD ceiling with 80%/100%/forecast alerts
- RAG: Alembic `0010_pgvector` needs the `vector` extension (supported on RDS Postgres 15.2+/16 when allowed)

## Destroy

Main stack first, then bootstrap (only if you also want to delete the state backend):

```bash
cd infra/aws
terraform destroy

# Optional — destroys the state bucket/lock table (download state first!)
cd bootstrap
terraform destroy
```
