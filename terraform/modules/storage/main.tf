# Storage Module - S3 + Glue Iceberg Catalog
# Stores raw (Bronze), cleaned (Silver), and aggregated (Gold) Iceberg tables.

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "project_name" {
  type        = string
  default     = "data-pipeline"
  description = "Project name used in resource naming"
}

variable "raw_retention_days" {
  type    = number
  default = 90
}

variable "silver_retention_days" {
  type    = number
  default = 365
}

variable "gold_retention_days" {
  type    = number
  default = 1825 # 5 years
}

variable "enable_versioning" {
  type    = bool
  default = true
}

# S3 buckets
resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Tier        = "bronze"
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "silver" {
  bucket = "${var.project_name}-silver-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Tier        = "silver"
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "gold" {
  bucket = "${var.project_name}-gold-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Tier        = "gold"
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "warehouse" {
  bucket = "${var.project_name}-warehouse-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Purpose     = "athena-query-results"
    Environment = var.environment
  }
}

# Versioning
resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  count  = var.enable_versioning ? 1 : 0
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "silver" {
  bucket = aws_s3_bucket.silver.id
  count  = var.enable_versioning ? 1 : 0
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "gold" {
  bucket = aws_s3_bucket.gold.id
  count  = var.enable_versioning ? 1 : 0
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle policies - move older data to Glacier
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "raw-tier-transition"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 60
      storage_class = "GLACIER"
    }

    expiration {
      days = var.raw_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id

  rule {
    id     = "silver-tier-transition"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    expiration {
      days = var.silver_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id

  rule {
    id     = "gold-tier-transition"
    status = "Enabled"

    transition {
      days          = 365
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = var.gold_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket                  = aws_s3_bucket.silver.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "gold" {
  bucket                  = aws_s3_bucket.gold.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Glue Iceberg Catalog database
resource "aws_glue_catalog_database" "iceberg" {
  name = "${var.project_name}_iceberg_${var.environment}"

  description = "Apache Iceberg v3 catalog database for the ${var.environment} environment"

  parameters = {
    "classification" = "iceberg"
  }
}

# Athena workgroup
resource "aws_athena_workgroup" "main" {
  name = "${var.project_name}-${var.environment}"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.warehouse.bucket}/results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = {
    Environment = var.environment
  }
}

data "aws_caller_identity" "current" {}

# --- Outputs ---

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "silver_bucket" {
  value = aws_s3_bucket.silver.bucket
}

output "gold_bucket" {
  value = aws_s3_bucket.gold.bucket
}

output "warehouse_bucket" {
  value = aws_s3_bucket.warehouse.bucket
}

output "iceberg_database" {
  value = aws_glue_catalog_database.iceberg.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.main.name
}
