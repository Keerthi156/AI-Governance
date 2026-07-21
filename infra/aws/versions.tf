terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state (optional). After bootstrap:
  #   1. cp backend.hcl.example backend.hcl  # fill from bootstrap outputs
  #   2. Uncomment the backend block below
  #   3. terraform init -migrate-state -backend-config=backend.hcl
  #
  # backend "s3" {
  #   # Values come from backend.hcl via -backend-config=
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
