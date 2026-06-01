# Root Terraform configuration for the dev environment
# Ties together VPC, storage (S3 + Iceberg catalog), IAM, ingestion, and observability.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Configure remote state backend here. For local dev, comment out.
    # bucket         = "your-tfstate-bucket"
    # key            = "data-pipeline/dev/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "your-tfstate-lock"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "cloud-native-data-pipeline"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

# --- Variables ---

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "project_name" {
  type    = string
  default = "data-pipeline"
}

variable "alarm_email" {
  type      = string
  sensitive = true
}

# --- Networking ---

module "vpc" {
  source = "../../modules/vpc"

  environment = var.environment
  vpc_cidr    = "10.0.0.0/16"
}

# --- Storage ---

module "storage" {
  source = "../../modules/storage"

  environment         = var.environment
  project_name        = var.project_name
  enable_versioning   = true
  raw_retention_days  = 90
  silver_retention_days = 365
  gold_retention_days = 1825
}

# --- IAM ---

module "iam" {
  source = "../../modules/iam"

  environment         = var.environment
  project_name        = var.project_name
  raw_bucket_arn      = "arn:aws:s3:::${module.storage.raw_bucket}"
  silver_bucket_arn   = "arn:aws:s3:::${module.storage.silver_bucket}"
  gold_bucket_arn     = "arn:aws:s3:::${module.storage.gold_bucket}"
  warehouse_bucket_arn = "arn:aws:s3:::${module.storage.warehouse_bucket}"
  iceberg_database    = module.storage.iceberg_database
}

# --- Ingestion Lambda ---

module "ingestion" {
  source = "../../modules/ingestion"

  environment     = var.environment
  project_name    = var.project_name
  raw_bucket      = module.storage.raw_bucket
  lambda_role_arn = module.iam.lambda_execution_role_arn
}

# --- Monitoring ---

module "monitoring" {
  source = "../../modules/monitoring"

  environment       = var.environment
  pipeline_name     = var.project_name
  alarm_email       = var.alarm_email
  ecs_cluster_name  = ""
  rds_instance_id   = ""
}

# --- Outputs ---

output "raw_bucket" {
  value = module.storage.raw_bucket
}

output "silver_bucket" {
  value = module.storage.silver_bucket
}

output "gold_bucket" {
  value = module.storage.gold_bucket
}

output "warehouse_bucket" {
  value = module.storage.warehouse_bucket
}

output "iceberg_database" {
  value = module.storage.iceberg_database
}

output "athena_workgroup" {
  value = module.storage.athena_workgroup
}

output "ingestion_lambda" {
  value = module.ingestion.ingestion_lambda_name
}
