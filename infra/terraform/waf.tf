resource "aws_wafv2_web_acl" "this" {
  name        = "${var.cluster_name}-web-acl"
  description = "WAF for ${var.cluster_name} ALB - rate-limit + OWASP core rules"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # ── Rate-limit: 100 requests per 5-minute window per IP ──────────────
  rule {
    name     = "rate-limit"
    priority = 0

    dynamic "action" {
      for_each = var.waf_action == "block" ? [1] : []
      content {
        block {}
      }
    }
    dynamic "action" {
      for_each = var.waf_action == "count" ? [1] : []
      content {
        count {}
      }
    }

    statement {
      rate_based_statement {
        limit              = 100
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.cluster_name}RateLimit"
      sampled_requests_enabled   = true
    }
  }

  # ── AWS Core Rule Set (SQLi, XSS, LFI, RFI, SSRF, etc.) ────────────
  rule {
    name     = "aws-core-rule-set"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.cluster_name}AwsCoreRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ── SQL Injection ────────────────────────────────────────────────────
  rule {
    name     = "aws-sql-rule-set"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.cluster_name}AwsSqlRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ── Known Bad Inputs (shellshock, JRuby, etc.) ──────────────────────
  rule {
    name     = "aws-known-bad-inputs"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.cluster_name}AwsKnownBadInputs"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.cluster_name}WebAcl"
    sampled_requests_enabled   = true
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-web-acl"
  })
}

# TODO: re-enable after debugging ARN validation
# resource "aws_wafv2_web_acl_logging_configuration" "this" {
#   log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
#   resource_arn            = aws_wafv2_web_acl.this.arn
# }

resource "aws_cloudwatch_log_group" "waf" {
  name              = "/aws/wafv2/${var.cluster_name}"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "/aws/wafv2/${var.cluster_name}"
  })
}
