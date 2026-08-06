data "aws_lb" "gateway" {
  tags = {
    "ingress.k8s.aws/stack" = "event-ticketing"
  }
}
locals {
  alb_domain  = data.aws_lb.gateway.dns_name
  alb_zone_id = data.aws_lb.gateway.zone_id
}
resource "aws_cloudfront_cache_policy" "no_cache" {
  name        = "event-ticketing-no-cache"
  comment     = "No caching at edge (TTL 0)"
  default_ttl = 0
  max_ttl     = 0
  min_ttl     = 0
  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}
resource "aws_cloudfront_cache_policy" "assets" {
  name        = "event-ticketing-assets"
  comment     = "Cache hashed bundles 1y"
  default_ttl = 31536000
  max_ttl     = 31536000
  min_ttl     = 31536000
  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}
resource "aws_cloudfront_origin_request_policy" "all_viewer" {
  name    = "event-ticketing-all-viewer"
  comment = "Forward all headers, cookies, query strings to origin"
  cookies_config {
    cookie_behavior = "all"
  }
  headers_config {
    header_behavior = "allViewer"
  }
  query_strings_config {
    query_string_behavior = "all"
  }
}
resource "aws_cloudfront_origin_request_policy" "assets" {
  name    = "event-ticketing-assets-origin-request"
  comment = "Forward nothing for static assets"
  cookies_config {
    cookie_behavior = "none"
  }
  headers_config {
    header_behavior = "none"
  }
  query_strings_config {
    query_string_behavior = "none"
  }
}
resource "aws_cloudfront_response_headers_policy" "no_cache" {
  name    = "event-ticketing-no-cache"
  comment = "Cache-Control: no-cache on index.html / SPA routes"
  custom_headers_config {
    items {
      header   = "Cache-Control"
      value    = "no-cache"
      override = true
    }
  }
}
resource "random_password" "cloudfront_secret" {
  length  = 32
  special = false
}
resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CloudFront distribution for Event Ticketing"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  aliases = []
  origin {
    domain_name = local.alb_domain
    origin_id   = "alb-gateway"
    custom_header {
      name  = "X-CloudFront-Secret"
      value = random_password.cloudfront_secret.result
    }
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  default_cache_behavior {
    target_origin_id           = "alb-gateway"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.no_cache.id
    origin_request_policy_id   = aws_cloudfront_origin_request_policy.all_viewer.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.no_cache.id
  }
  ordered_cache_behavior {
    path_pattern             = "/assets/*"
    target_origin_id         = "alb-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = aws_cloudfront_cache_policy.assets.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.assets.id
  }
  ordered_cache_behavior {
    path_pattern           = "/v1/*"
    target_origin_id       = "alb-gateway"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id          = aws_cloudfront_cache_policy.no_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.all_viewer.id
  }
  ordered_cache_behavior {
    path_pattern           = "/ws/*"
    target_origin_id       = "alb-gateway"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id          = aws_cloudfront_cache_policy.no_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.all_viewer.id
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
