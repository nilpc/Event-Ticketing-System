resource "aws_budgets_budget" "monthly" {
  name              = "${var.cluster_name}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = "150"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-07-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["admin+event-ticketing@example.com"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["admin+event-ticketing@example.com"]
  }

  tags = var.tags
}

resource "aws_budgets_budget" "forecast" {
  name              = "${var.cluster_name}-forecast-budget"
  budget_type       = "COST"
  limit_amount      = "150"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-07-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["admin+event-ticketing@example.com"]
  }

  tags = var.tags
}
