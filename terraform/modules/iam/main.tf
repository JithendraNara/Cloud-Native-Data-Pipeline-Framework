# IAM Module - Roles and policies for the data pipeline
variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "data-pipeline"
}

variable "raw_bucket_arn" {
  type = string
}

variable "silver_bucket_arn" {
  type = string
}

variable "gold_bucket_arn" {
  type = string
}

variable "warehouse_bucket_arn" {
  type = string
}

variable "iceberg_database" {
  type = string
}

# Trust policy for Lambda, Glue, Airflow workers
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

# Base permissions policy for pipeline execution
data "aws_iam_policy_document" "pipeline_base" {
  # S3 access - all 4 buckets
  statement {
    sid    = "S3Access"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetObjectVersion",
      "s3:PutObjectAcl",
    ]

    resources = [
      var.raw_bucket_arn,
      "${var.raw_bucket_arn}/*",
      var.silver_bucket_arn,
      "${var.silver_bucket_arn}/*",
      var.gold_bucket_arn,
      "${var.gold_bucket_arn}/*",
      var.warehouse_bucket_arn,
      "${var.warehouse_bucket_arn}/*",
    ]
  }

  # Glue Catalog access
  statement {
    sid    = "GlueCatalogAccess"
    effect = "Allow"

    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:GetTable",
      "glue:GetTables",
      "glue:DeleteTable",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreatePartition",
      "glue:UpdatePartition",
      "glue:DeletePartition",
    ]

    resources = ["*"]
  }

  # Athena query access
  statement {
    sid    = "AthenaQueryAccess"
    effect = "Allow"

    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
    ]

    resources = ["*"]
  }

  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:*:*:*"]
  }

  # KMS for encryption
  statement {
    sid    = "KMSDecrypt"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]

    resources = ["*"]
  }
}

# Lambda execution role
resource "aws_iam_role" "lambda_execution" {
  name               = "${var.project_name}-lambda-exec-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_pipeline" {
  name   = "${var.project_name}-pipeline-access"
  role   = aws_iam_role.lambda_execution.id
  policy = data.aws_iam_policy_document.pipeline_base.json
}

# Glue job role
resource "aws_iam_role" "glue_execution" {
  name               = "${var.project_name}-glue-exec-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "glue_basic" {
  role       = aws_iam_role.glue_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_pipeline" {
  name   = "${var.project_name}-glue-pipeline-access"
  role   = aws_iam_role.glue_execution.id
  policy = data.aws_iam_policy_document.pipeline_base.json
}

# Airflow EC2 / ECS task role
resource "aws_iam_role" "airflow_execution" {
  name               = "${var.project_name}-airflow-exec-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "airflow_pipeline" {
  name   = "${var.project_name}-airflow-pipeline-access"
  role   = aws_iam_role.airflow_execution.id
  policy = data.aws_iam_policy_document.pipeline_base.json
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "airflow" {
  name = "${var.project_name}-airflow-profile-${var.environment}"
  role = aws_iam_role.airflow_execution.name
}

# AI analyst Lambda role (MiniMax-powered query agent)
resource "aws_iam_role" "analyst_lambda" {
  name               = "${var.project_name}-analyst-lambda-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Environment = var.environment
    Purpose     = "ai-data-analyst"
  }
}

resource "aws_iam_role_policy_attachment" "analyst_basic" {
  role       = aws_iam_role.analyst_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "analyst_pipeline" {
  name   = "${var.project_name}-analyst-access"
  role   = aws_iam_role.analyst_lambda.id
  policy = data.aws_iam_policy_document.pipeline_base.json
}

# --- Outputs ---

output "lambda_execution_role_arn" {
  value = aws_iam_role.lambda_execution.arn
}

output "glue_execution_role_arn" {
  value = aws_iam_role.glue_execution.arn
}

output "airflow_execution_role_arn" {
  value = aws_iam_role.airflow_execution.arn
}

output "airflow_instance_profile" {
  value = aws_iam_instance_profile.airflow.name
}

output "analyst_lambda_role_arn" {
  value = aws_iam_role.analyst_lambda.arn
}
