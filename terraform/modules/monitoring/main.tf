# Monitoring Module - CloudWatch Alarms & SNS
variable "environment" { type = string }
variable "alarm_email" { type = string }
variable "pipeline_name" { type = string, default = "etl-pipeline" }
variable "rds_instance_id" { type = string, default = "" }
variable "ecs_cluster_name" { type = string, default = "" }

output "sns_topic_arn" { value = aws_sns_topic.pipeline_alerts.arn }
output "log_group_name" { value = aws_cloudwatch_log_group.pipeline.name }

resource "aws_sns_topic" "pipeline_alerts" {
  name = "pipeline-alerts-${var.environment}"
  tags = { Environment = var.environment }
}

resource "aws_sns_topic_subscription" "email_target" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol = "email"
  endpoint = var.alarm_email
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name = "/aws/${var.pipeline_name}/${var.environment}"
  retention_in_days = 14
  tags = { Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  count = var.rds_instance_id != "" ? 1 : 0
  alarm_name = "${var.pipeline_name}-rds-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "2"
  metric_name = "CPUUtilization"
  namespace = "AWS/RDS"
  period = "300"
  statistic = "Average"
  threshold = 80
  alarm_actions = [aws_sns_topic.pipeline_alerts.arn]
  dimensions = { DBInstanceIdentifier = var.rds_instance_id }
}

resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  count = var.rds_instance_id != "" ? 1 : 0
  alarm_name = "${var.pipeline_name}-rds-storage-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "2"
  metric_name = "FreeStorageSpace"
  namespace = "AWS/RDS"
  period = "300"
  statistic = "Average"
  threshold = 85
  alarm_actions = [aws_sns_topic.pipeline_alerts.arn]
  dimensions = { DBInstanceIdentifier = var.rds_instance_id }
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  count = var.ecs_cluster_name != "" ? 1 : 0
  alarm_name = "${var.pipeline_name}-ecs-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "2"
  metric_name = "CPUUtilization"
  namespace = "AWS/ECS"
  period = "300"
  statistic = "Average"
  threshold = 80
  alarm_actions = [aws_sns_topic.pipeline_alerts.arn]
  dimensions = { ClusterName = var.ecs_cluster_name }
}

resource "aws_cloudwatch_metric_alarm" "pipeline_failed_tasks" {
  count = var.ecs_cluster_name != "" ? 1 : 0
  alarm_name = "${var.pipeline_name}-failed-tasks-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "1"
  metric_name = "FailedTasks"
  namespace = "AWS/ECS"
  period = "300"
  statistic = "Sum"
  threshold = 1
  alarm_actions = [aws_sns_topic.pipeline_alerts.arn]
  dimensions = { ClusterName = var.ecs_cluster_name }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.pipeline_name}-dashboard-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title = "RDS Metrics"
          metrics = [["AWS/RDS", "CPUUtilization", { stat = "Average" }], [".", "DatabaseConnections", { stat = "Maximum" }]]
          period = 300
        }
      },
      {
        type = "metric"
        properties = {
          title = "ECS Metrics"
          metrics = [["AWS/ECS", "CPUUtilization", { stat = "Average" }], [".", "MemoryUtilization", { stat = "Average" }]]
          period = 300
        }
      }
    ]
  })
}
