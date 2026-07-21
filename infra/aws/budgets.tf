# Optional AWS Budgets — monthly cost ceiling with SNS / email alerts.
# Default off. Confirm SNS email after apply if using a topic subscription.

locals {
  budget_enabled = var.enable_aws_budget
  budget_email = (
    var.budget_notification_email != ""
    ? var.budget_notification_email
    : var.alarm_notification_email
  )
}

resource "aws_sns_topic" "budget" {
  count = local.budget_enabled ? 1 : 0

  name = "${local.name_prefix}-budget-alerts"

  tags = { Name = "${local.name_prefix}-budget-alerts" }
}

resource "aws_sns_topic_policy" "budget" {
  count = local.budget_enabled ? 1 : 0

  arn = aws_sns_topic.budget[0].arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAWSBudgetsPublish"
        Effect = "Allow"
        Principal = {
          Service = "budgets.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.budget[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "budget_email" {
  count = local.budget_enabled && local.budget_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.budget[0].arn
  protocol  = "email"
  endpoint  = local.budget_email
}

resource "aws_budgets_budget" "monthly" {
  count = local.budget_enabled ? 1 : 0

  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    use_amortized              = false
    use_blended                = false
  }

  # Actual spend ≥ 80% of budget
  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 80
    threshold_type      = "PERCENTAGE"
    notification_type   = "ACTUAL"

    subscriber_sns_topic_arns = [aws_sns_topic.budget[0].arn]
    subscriber_email_addresses = (
      local.budget_email != "" ? [local.budget_email] : []
    )
  }

  # Actual spend ≥ 100% of budget
  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 100
    threshold_type      = "PERCENTAGE"
    notification_type   = "ACTUAL"

    subscriber_sns_topic_arns = [aws_sns_topic.budget[0].arn]
    subscriber_email_addresses = (
      local.budget_email != "" ? [local.budget_email] : []
    )
  }

  # Forecasted spend ≥ 100% of budget
  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 100
    threshold_type      = "PERCENTAGE"
    notification_type   = "FORECASTED"

    subscriber_sns_topic_arns = [aws_sns_topic.budget[0].arn]
    subscriber_email_addresses = (
      local.budget_email != "" ? [local.budget_email] : []
    )
  }

  depends_on = [aws_sns_topic_policy.budget]
}
