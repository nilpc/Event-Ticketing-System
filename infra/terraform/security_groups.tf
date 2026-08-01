resource "aws_security_group" "cluster" {
  name        = "${var.cluster_name}-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-cluster-sg"
  })
}

resource "aws_security_group" "node" {
  name        = "${var.cluster_name}-node-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-node-sg"
  })
}

resource "aws_vpc_security_group_egress_rule" "node_all_outbound" {
  security_group_id = aws_security_group.node.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound traffic from nodes"
}

resource "aws_vpc_security_group_ingress_rule" "node_https_from_vpc" {
  security_group_id = aws_security_group.node.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Allow HTTPS from VPC (API server)"
}

resource "aws_vpc_security_group_ingress_rule" "node_self_all" {
  security_group_id            = aws_security_group.node.id
  referenced_security_group_id = aws_security_group.node.id
  ip_protocol                  = "-1"
  description                  = "Allow all traffic between nodes"
}

resource "aws_vpc_security_group_ingress_rule" "node_web_from_alb" {
  security_group_id = aws_security_group.node.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 30000
  to_port           = 32767
  ip_protocol       = "tcp"
  description       = "Allow NodePort range from VPC (ALB health checks)"
}

# ── ALB ingress SG: CloudFront only ──────────────────────────────────────
# Forces ALL external traffic through CloudFront (cheaper egress + caching).
# Referenced by the ALB ingress annotation alb.ingress.kubernetes.io/security-groups,
# which overrides the controller-created 0.0.0.0/0 SG.
data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "alb" {
  name        = "${var.cluster_name}-alb-sg"
  description = "ALB ingress: HTTP/HTTPS only from CloudFront"
  vpc_id      = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-alb-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "alb_http_from_cloudfront" {
  security_group_id = aws_security_group.alb.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "Allow HTTP from CloudFront only"
}

resource "aws_vpc_security_group_egress_rule" "alb_all_outbound" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound from ALB"
}

resource "aws_security_group" "rds" {
  name        = "${var.cluster_name}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-rds-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "rds_postgres_from_nodes" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.node.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "Allow PostgreSQL from EKS nodes"
}

resource "aws_vpc_security_group_egress_rule" "rds_all_outbound" {
  security_group_id = aws_security_group.rds.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound from RDS"
}
