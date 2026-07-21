# Optional CloudWatch alarms + SNS email notifications.
# Default off to avoid alarm noise / email confirmations on first demos.

locals {
  alarms_enabled = var.enable_cloudwatch_alarms
  alarm_actions  = local.alarms_enabled && length(aws_sns_topic.alarms) > 0 ? [aws_sns_topic.alarms[0].arn] : []
}

resource "aws_sns_topic" "alarms" {
  count = local.alarms_enabled ? 1 : 0

  name = "${local.name_prefix}-alarms"

  tags = { Name = "${local.name_prefix}-alarms" }
}

resource "aws_sns_topic_subscription" "alarms_email" {
  count = local.alarms_enabled && var.alarm_notification_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_notification_email
}

# ---------------------------------------------------------------------------
# ALB
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-alb-5xx"
  alarm_description   = "ALB target 5xx responses elevated"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = var.alarm_alb_5xx_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-alb-5xx" }
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_backend" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-alb-unhealthy-backend"
  alarm_description   = "Backend target group has unhealthy hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-alb-unhealthy-backend" }
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_frontend" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-alb-unhealthy-frontend"
  alarm_description   = "Frontend target group has unhealthy hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.frontend.arn_suffix
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-alb-unhealthy-frontend" }
}

# ---------------------------------------------------------------------------
# ECS (Container Insights / service CPU)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "ecs_backend_cpu" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-ecs-backend-cpu"
  alarm_description   = "Backend ECS service CPU high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.alarm_ecs_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.backend.name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-ecs-backend-cpu" }
}

resource "aws_cloudwatch_metric_alarm" "ecs_frontend_cpu" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-ecs-frontend-cpu"
  alarm_description   = "Frontend ECS service CPU high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.alarm_ecs_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.frontend.name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-ecs-frontend-cpu" }
}

# ---------------------------------------------------------------------------
# RDS
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-rds-free-storage"
  alarm_description   = "RDS free storage below threshold"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.alarm_rds_free_storage_bytes
  treat_missing_data  = "breaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-rds-free-storage" }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  count = local.alarms_enabled ? 1 : 0

  alarm_name          = "${local.name_prefix}-rds-cpu"
  alarm_description   = "RDS CPU high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = var.alarm_rds_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = { Name = "${local.name_prefix}-rds-cpu" }
}
