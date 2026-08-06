locals {
  has_domain = var.domain_name != ""
}
data "aws_route53_zone" "this" {
  count = local.has_domain ? 1 : 0
  name         = var.domain_name
  private_zone = false
}
resource "aws_acm_certificate" "this" {
  count = local.has_domain ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"
  tags = merge(var.tags, {
    Name = "${var.cluster_name}-cert"
  })
}
resource "aws_route53_record" "validation" {
  count = local.has_domain ? 1 : 0
  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = tolist(aws_acm_certificate.this[0].domain_validation_options)[0].resource_record_name
  type    = tolist(aws_acm_certificate.this[0].domain_validation_options)[0].resource_record_type
  records = [tolist(aws_acm_certificate.this[0].domain_validation_options)[0].resource_record_value]
  ttl     = 60
}
resource "aws_acm_certificate_validation" "this" {
  count = local.has_domain ? 1 : 0
  certificate_arn         = aws_acm_certificate.this[0].arn
  validation_record_fqdns = aws_route53_record.validation[*].fqdn
}
