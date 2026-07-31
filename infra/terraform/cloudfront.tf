# ── CloudFront ────────────────────────────────────────────────────────────
# Provides HTTPS via *.cloudfront.net (no custom domain required).
# Origin: internet-facing ALB created by AWS Load Balancer Controller.

data "aws_lb" "gateway" {
  tags = {
    # Group-mode ingress: ALB controller tags the shared-group ALB with the
    # group name only (not "namespace/ingress-name").
    "ingress.k8s.aws/stack" = "event-ticketing"
  }
}

locals {
  alb_domain = data.aws_lb.gateway.dns_name
  alb_zone_id = data.aws_lb.gateway.zone_id
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CloudFront distribution for Event Ticketing"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # US + Europe only (cheapest)

  # HTTP → HTTPS redirect
  aliases = []

  origin {
    domain_name = local.alb_domain
    origin_id   = "alb-gateway"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"   # ALB is HTTP-only
      origin_ssl_protocols     = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "alb-gateway"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = true
      headers      = ["Origin", "Authorization", "Content-Type", "X-Requested-With"]
      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Cache policy for API/WS paths (no caching)
  ordered_cache_behavior {
    path_pattern           = "/v1/*"
    target_origin_id       = "alb-gateway"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = true
      headers      = ["Origin", "Authorization", "Content-Type", "X-Requested-With"]
      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  ordered_cache_behavior {
    path_pattern           = "/ws/*"
    target_origin_id       = "alb-gateway"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = true
      headers      = ["Origin"]
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-cloudfront"
  })
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name (HTTPS)"
  value       = aws_cloudfront_distribution.this.domain_name
}

output "cloudfront_origin_alb" {
  description = "Origin ALB DNS name"
  value       = local.alb_domain
}
