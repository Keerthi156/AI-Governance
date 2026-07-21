# Bootstrap stack — creates remote Terraform state backend (S3 + DynamoDB).
# Apply this ONCE with local state, then point the main infra/aws stack at it.
#
#   cd infra/aws/bootstrap
#   terraform init && terraform apply
#   # then migrate main stack — see ../README.md

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      Purpose   = "terraform-remote-state"
      ManagedBy = "terraform"
    }
  }
}

variable "project_name" {
  type    = string
  default = "ai-gov"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket for Terraform state. Empty = auto from account id."
  default     = ""
}

data "aws_caller_identity" "current" {}

locals {
  state_bucket = (
    var.state_bucket_name != ""
    ? var.state_bucket_name
    : "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"
  )
  lock_table = "${var.project_name}-terraform-locks"
}

resource "aws_s3_bucket" "tfstate" {
  bucket = local.state_bucket

  tags = { Name = local.state_bucket }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Deny non-TLS access to state objects
resource "aws_s3_bucket_policy" "tfstate_tls" {
  bucket = aws_s3_bucket.tfstate.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.tfstate.arn,
          "${aws_s3_bucket.tfstate.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

resource "aws_dynamodb_table" "tf_locks" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = { Name = local.lock_table }
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}

output "dynamodb_table" {
  value = aws_dynamodb_table.tf_locks.name
}

output "aws_region" {
  value = var.aws_region
}

output "backend_hcl_snippet" {
  description = "Paste into infra/aws/backend.hcl after bootstrap"
  value       = <<-EOT
    bucket         = "${aws_s3_bucket.tfstate.bucket}"
    key            = "prod/terraform.tfstate"
    region         = "${var.aws_region}"
    dynamodb_table = "${aws_dynamodb_table.tf_locks.name}"
    encrypt        = true
  EOT
}
