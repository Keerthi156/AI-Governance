#!/usr/bin/env bash
# Bootstrap: push first images to ECR then force ECS redeploy.
# Prerequisites: AWS CLI + Docker + Terraform already applied (ECR + ECS exist).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AWS_DIR="$ROOT/infra/aws"

cd "$AWS_DIR"
REGION="$(terraform output -raw aws_region)"
ACCOUNT="$(terraform output -raw aws_account_id)"
API_BASE="$(terraform output -raw api_base_url)"
BACKEND_REPO="$(terraform output -raw ecr_backend_repository_url)"
FRONTEND_REPO="$(terraform output -raw ecr_frontend_repository_url)"
CLUSTER="$(terraform output -raw ecs_cluster_name)"
BACKEND_SVC="$(terraform output -raw ecs_backend_service_name)"
FRONTEND_SVC="$(terraform output -raw ecs_frontend_service_name)"

echo "Logging into ECR ($REGION)..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

echo "Building + pushing backend..."
docker build -t "$BACKEND_REPO:latest" "$ROOT/backend"
docker push "$BACKEND_REPO:latest"

echo "Building + pushing frontend (API=$API_BASE)..."
docker build \
  --build-arg "NEXT_PUBLIC_API_BASE_URL=$API_BASE" \
  -t "$FRONTEND_REPO:latest" \
  "$ROOT/frontend"
docker push "$FRONTEND_REPO:latest"

echo "Forcing ECS redeploy..."
aws ecs update-service --cluster "$CLUSTER" --service "$BACKEND_SVC" --force-new-deployment --region "$REGION" >/dev/null
aws ecs update-service --cluster "$CLUSTER" --service "$FRONTEND_SVC" --force-new-deployment --region "$REGION" >/dev/null

echo "Done. App URL:"
terraform output -raw app_url
echo
