output "alb_dns_name" {
  description = "Public ALB hostname"
  value       = aws_lb.main.dns_name
}

output "app_url" {
  description = "Frontend URL (https when domain_name is set)"
  value       = local.public_base_url
}

output "api_base_url" {
  description = "Backend API base URL for NEXT_PUBLIC_API_BASE_URL builds"
  value       = local.public_api_base_url
}

output "https_enabled" {
  value = local.enable_https
}

output "domain_name" {
  value = var.domain_name
}

output "acm_certificate_arn" {
  value = local.enable_https ? local.https_certificate_arn : null
}

output "ecr_backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "ecs_frontend_service_name" {
  value = aws_ecs_service.frontend.name
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "rds_multi_az" {
  description = "Whether RDS Multi-AZ standby is enabled"
  value       = aws_db_instance.main.multi_az
}

output "rds_backup_retention_days" {
  value = aws_db_instance.main.backup_retention_period
}

output "waf_enabled" {
  value = var.enable_waf
}

output "waf_web_acl_arn" {
  description = "WAFv2 Web ACL ARN when enable_waf is true"
  value       = var.enable_waf ? aws_wafv2_web_acl.alb[0].arn : null
}

output "github_deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC (set as AWS_DEPLOY_ROLE_ARN)"
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy[0].arn : null
}

output "alb_ingress_cidr_blocks" {
  description = "CIDRs currently allowed to reach the ALB"
  value       = var.alb_ingress_cidr_blocks
}

output "cloudwatch_alarms_enabled" {
  value = var.enable_cloudwatch_alarms
}

output "alarms_sns_topic_arn" {
  description = "SNS topic for CloudWatch alarm notifications"
  value       = var.enable_cloudwatch_alarms ? aws_sns_topic.alarms[0].arn : null
}

output "aws_budget_enabled" {
  value = var.enable_aws_budget
}

output "monthly_budget_usd" {
  value = var.enable_aws_budget ? var.monthly_budget_usd : null
}

output "budget_sns_topic_arn" {
  description = "SNS topic for AWS Budgets alerts"
  value       = var.enable_aws_budget ? aws_sns_topic.budget[0].arn : null
}

output "secrets_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "aws_region" {
  value = var.aws_region
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}
