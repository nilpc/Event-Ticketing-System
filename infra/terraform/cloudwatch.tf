locals {
  cw_dashboard_name = "${var.cluster_name}-operations"
}
resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = local.cw_dashboard_name
  dashboard_body = jsonencode({
    start          = "-PT6H"
    periodOverride = "auto"
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/EKS", "node_count_total", { stat = "Average", label = "Nodes" }],
            [".", "cluster_failed_node_count", { stat = "Average", label = "Failed Nodes" }]
          ]
          region = var.aws_region
          title  = "EKS Node Count"
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 0
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/NATGateway", "BytesOutToDestination", { stat = "Sum", label = "Bytes Out" }],
            [".", "BytesInFromDestination", { stat = "Sum", label = "Bytes In" }]
          ]
          region = var.aws_region
          title  = "NAT Gateway Traffic"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Requests" }]
          ]
          region = var.aws_region
          title  = "ALB Request Count"
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 6
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "p95", label = "p95 Latency" }],
            [".", "TargetResponseTime", { stat = "p99", label = "p99 Latency" }]
          ]
          region = var.aws_region
          title  = "ALB Target Response Time"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "DatabaseConnections", { label = "Connections" }]
          ]
          region = var.aws_region
          title  = "RDS Connections"
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 12
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "CPUUtilization", { stat = "Average", label = "CPU %" }],
            [".", "FreeableMemory", { stat = "Average", label = "Free Memory Bytes", yAxis = "right" }]
          ]
          region = var.aws_region
          title  = "RDS CPU / Memory"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/WAFV2", "BlockedRequests", { stat = "Sum", label = "Blocked" }],
            [".", "AllowedRequests", { stat = "Sum", label = "Allowed" }]
          ]
          region = var.aws_region
          title  = "WAF Request Action"
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 18
        width  = 6
        height = 6
        properties = {
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/Billing", "EstimatedCharges", { stat = "Maximum", label = "Estimated Charges ($)" }]
          ]
          region               = var.aws_region
          title                = "Estimated AWS Charges"
          setPeriodToTimeRange = true
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 24
        width  = 12
        height = 2
        properties = {
          markdown = "## Event Ticketing — Operations Dashboard\n\nMetrics auto-refresh every 5 minutes. Budget alarm: $150/mo."
        }
      }
    ]
  })
}
