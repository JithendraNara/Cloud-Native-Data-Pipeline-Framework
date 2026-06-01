# Ingestion Module - Lambda function for event-driven data ingestion
variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "data-pipeline"
}

variable "raw_bucket" {
  type = string
}

variable "lambda_role_arn" {
  type = string
}

variable "lambda_zip_path" {
  type    = string
  default = "../../../lambda/ingestion/deployment.zip"
}

variable "memory_size" {
  type    = number
  default = 512
}

variable "timeout" {
  type    = number
  default = 300
}

resource "aws_lambda_function" "ingestion" {
  function_name = "${var.project_name}-ingestion-${var.environment}"
  role          = var.lambda_role_arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  filename      = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  memory_size = var.memory_size
  timeout     = var.timeout

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      RAW_BUCKET    = var.raw_bucket
      TABLE_PREFIX  = "raw"
      LOG_LEVEL     = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Environment = var.environment
    Module      = "ingestion"
  }
}

# EventBridge rule for scheduled ingestion (every 6 hours)
resource "aws_cloudwatch_event_rule" "ingestion_schedule" {
  name                = "${var.project_name}-ingestion-schedule-${var.environment}"
  description         = "Triggers data ingestion every 6 hours"
  schedule_expression = "rate(6 hours)"

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "ingestion_lambda" {
  rule      = aws_cloudwatch_event_rule.ingestion_schedule.name
  target_id = "${var.project_name}-ingestion-${var.environment}"
  arn       = aws_lambda_function.ingestion.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ingestion_schedule.arn
}

# S3 trigger for new raw files
resource "aws_s3_bucket_notification" "raw_trigger" {
  bucket = var.raw_bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}

resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "s3.amazonaws.com"
  source_bucket = var.raw_bucket
}

# --- Outputs ---

output "ingestion_lambda_arn" {
  value = aws_lambda_function.ingestion.arn
}

output "ingestion_lambda_name" {
  value = aws_lambda_function.ingestion.function_name
}
