variable "project_name" {
  type        = string
  description = "Short project prefix for resource names"
  default     = "ai-gov"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "prod"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "db_username" {
  type    = string
  default = "ai_governance"
}

variable "db_name" {
  type    = string
  default = "ai_governance"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance size"
  default     = "db.t4g.micro"
}

variable "db_multi_az" {
  type        = bool
  description = "Enable Multi-AZ standby for RDS (HA). Doubles instance cost; recommended for prod."
  default     = false
}

variable "db_backup_retention_days" {
  type        = number
  nullable    = true
  description = "Automated backup retention (0–35). Null = 7 for prod, 1 otherwise."
  default     = null

  validation {
    condition = (
      var.db_backup_retention_days == null ||
      (var.db_backup_retention_days >= 0 && var.db_backup_retention_days <= 35)
    )
    error_message = "db_backup_retention_days must be null or between 0 and 35."
  }
}

variable "db_deletion_protection" {
  type        = bool
  nullable    = true
  description = "Prevent accidental RDS delete. Null = true when environment is prod."
  default     = null
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "frontend_cpu" {
  type    = number
  default = 256
}

variable "frontend_memory" {
  type    = number
  default = 512
}

variable "backend_desired_count" {
  type    = number
  default = 1
}

variable "frontend_desired_count" {
  type    = number
  default = 1
}

variable "jwt_secret_key" {
  type        = string
  description = "JWT signing secret (store in TF_VAR_jwt_secret_key / CI secrets)"
  sensitive   = true
}

variable "openai_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "anthropic_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "google_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "groq_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Use NAT for private subnet egress (recommended for prod)"
  default     = true
}

variable "domain_name" {
  type        = string
  description = "Custom domain for HTTPS (e.g. app.example.com). Empty = HTTP-only ALB DNS."
  default     = ""
}

variable "hosted_zone_id" {
  type        = string
  description = "Route53 hosted zone ID for ACM DNS validation + alias records. Required when creating a new ACM cert."
  default     = ""
}

variable "acm_certificate_arn" {
  type        = string
  description = "Optional existing ACM cert ARN (same region as ALB). Skips new certificate creation."
  default     = ""
}

variable "enable_waf" {
  type        = bool
  description = "Attach AWS WAFv2 Web ACL to the ALB (managed rules + rate limit)"
  default     = false
}

variable "waf_rate_limit" {
  type        = number
  description = "Max requests per IP per 5 minutes before WAF blocks (rate-based rule)"
  default     = 2000

  validation {
    condition     = var.waf_rate_limit >= 100 && var.waf_rate_limit <= 2000000000
    error_message = "waf_rate_limit must be between 100 and 2000000000."
  }
}

variable "enable_github_oidc" {
  type        = bool
  description = "Create IAM role assumable by GitHub Actions via OIDC (no static AWS keys)"
  default     = false
}

variable "create_github_oidc_provider" {
  type        = bool
  description = "Create the account-level GitHub OIDC provider. Set false if one already exists."
  default     = true
}

variable "github_repository" {
  type        = string
  description = "GitHub repo in owner/name form (required when enable_github_oidc is true)"
  default     = ""
}

variable "github_oidc_subject_patterns" {
  type        = list(string)
  description = "Allowed token.actions.githubusercontent.com:sub suffixes after repo:owner/name: (e.g. *, ref:refs/heads/main)"
  default     = ["*"]
}

variable "alb_ingress_cidr_blocks" {
  type        = list(string)
  description = "IPv4 CIDRs allowed to reach the ALB on :80/:443. Default open; set office/VPN CIDRs for lockdown."
  default     = ["0.0.0.0/0"]

  validation {
    condition = length(var.alb_ingress_cidr_blocks) > 0 && alltrue([
      for c in var.alb_ingress_cidr_blocks : can(cidrhost(c, 0))
    ])
    error_message = "alb_ingress_cidr_blocks must be a non-empty list of valid IPv4 CIDRs (e.g. 203.0.113.0/24)."
  }
}

variable "alb_ingress_ipv6_cidr_blocks" {
  type        = list(string)
  description = "Optional IPv6 CIDRs for ALB ingress. Empty = IPv6 not opened."
  default     = []
}

variable "enable_cloudwatch_alarms" {
  type        = bool
  description = "Create CloudWatch alarms (ALB 5xx/unhealthy, ECS CPU, RDS storage/CPU) + SNS topic"
  default     = false
}

variable "alarm_notification_email" {
  type        = string
  description = "Email for SNS alarm notifications (must confirm subscription in inbox). Empty = topic only."
  default     = ""
}

variable "alarm_alb_5xx_threshold" {
  type        = number
  description = "ALB target 5xx count (Sum, 1 min) before alarm"
  default     = 10
}

variable "alarm_ecs_cpu_threshold" {
  type        = number
  description = "ECS service average CPU % threshold"
  default     = 80
}

variable "alarm_rds_cpu_threshold" {
  type        = number
  description = "RDS average CPU % threshold"
  default     = 80
}

variable "alarm_rds_free_storage_bytes" {
  type        = number
  description = "Alarm when RDS FreeStorageSpace falls below this many bytes (default 2 GiB)"
  default     = 2147483648
}

variable "enable_aws_budget" {
  type        = bool
  description = "Create a monthly AWS Cost budget with SNS/email alerts"
  default     = false
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly cost budget limit in USD (account-level COST budget)"
  default     = 100

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be greater than 0."
  }
}

variable "budget_notification_email" {
  type        = string
  description = "Email for budget alerts. Falls back to alarm_notification_email when empty."
  default     = ""
}
