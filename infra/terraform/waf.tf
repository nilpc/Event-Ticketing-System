resource "aws_wafv2_web_acl" "this" {
  name        = "${var.cluster_name}-web-acl"
  description = "WAF for ${var.cluster_name} ALB - rate-limit + OWASP core rules"
  scope       = "REGIONAL"
  default_action {
    allow {}
  }
  rule {
    name     = "require-cloudfront-secret"
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
      and_statement {
        statement {
          not_statement {
            statement {
              byte_match_statement {
                field_to_match {
                  single_header {
                    name = "x-cloudfront-secret"
                  }
                }
                positional_constraint = "EXACTLY"
                search_string         = random_password.cloudfront_secret.result
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
        statement {
          not_statement {
            statement {
              byte_match_statement {
                field_to_match {
                  uri_path {}
                }
                positional_constraint = "STARTS_WITH"
                search_string         = "/health"
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
        statement {
          not_statement {
            statement {
              byte_match_statement {
                field_to_match {
                  uri_path {}
                }
                positional_constraint = "STARTS_WITH"
                search_string         = "/ready"
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.cluster_name}RequireCloudFrontSecret"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "rate-limit"
    priority = 1
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
  rule {
    name     = "aws-core-rule-set"
    priority = 2
    dynamic "override_action" {
      for_each = var.waf_action == "count" ? [1] : []
      content {
        count {}
      }
    }
    dynamic "override_action" {
      for_each = var.waf_action == "block" ? [1] : []
      content {
        none {}
      }
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
  rule {
    name     = "aws-sql-rule-set"
    priority = 3
    dynamic "override_action" {
      for_each = var.waf_action == "count" ? [1] : []
      content {
        count {}
      }
    }
    dynamic "override_action" {
      for_each = var.waf_action == "block" ? [1] : []
      content {
        none {}
      }
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
  rule {
    name     = "aws-known-bad-inputs"
    priority = 4
    dynamic "override_action" {
      for_each = var.waf_action == "count" ? [1] : []
      content {
        count {}
      }
    }
    dynamic "override_action" {
      for_each = var.waf_action == "block" ? [1] : []
      content {
        none {}
      }
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
resource "aws_cloudwatch_log_group" "waf" {
  name              = "/aws/wafv2/${var.cluster_name}"
  retention_in_days = 30
  tags = merge(var.tags, {
    Name = "/aws/wafv2/${var.cluster_name}"
  })
}
