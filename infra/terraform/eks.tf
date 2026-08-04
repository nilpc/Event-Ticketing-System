resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.eks_version
  role_arn = aws_iam_role.cluster.arn

  upgrade_policy {
    support_type = "STANDARD"
  }

  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = ["0.0.0.0/0"]
    security_group_ids      = [aws_security_group.cluster.id]
  }

  tags = merge(var.tags, {
    Name = var.cluster_name
  })
}

# OIDC provider for IRSA (IAM Roles for Service Accounts)
data "tls_certificate" "this" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "this" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.this.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-oidc-provider"
  })
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "vpc-cni"
  addon_version = "v1.22.4-eksbuild.3"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "coredns"
  addon_version = "v1.13.2-eksbuild.11"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "kube-proxy"
  addon_version = "v1.35.3-eksbuild.17"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "aws-ebs-csi-driver"
  addon_version = "v1.63.1-eksbuild.1"

  configuration_values = jsonencode({
    controller = {
      replicaCount = 1
    }
  })

  depends_on = [aws_iam_openid_connect_provider.this]
}

resource "aws_eks_addon" "metrics_server" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "metrics-server"
  addon_version = "v0.9.0-eksbuild.5"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_node_group" "on_demand" {
  cluster_name           = aws_eks_cluster.this.name
  node_group_name_prefix = "${var.cluster_name}-on-demand-${replace(var.eks_version, ".", "-")}-"
  node_role_arn          = aws_iam_role.node.arn
  subnet_ids             = aws_subnet.private[*].id

  instance_types = var.on_demand_instance_types

  scaling_config {
    desired_size = var.on_demand_desired_size
    min_size     = var.on_demand_min_size
    max_size     = var.on_demand_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "node-type"     = "on-demand"
    "capacity-type" = "on-demand"
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-on-demand"
  })

  depends_on = [aws_eks_cluster.this]

  lifecycle {
    create_before_destroy = true
  }
}



# Fargate profile for the event-ticketing namespace.
# Use Fargate when you want zero node management for control-plane pods.
# Not enabled by default to keep costs minimal — toggle var.fargate_enabled.
resource "aws_eks_fargate_profile" "this" {
  count = var.fargate_enabled ? 1 : 0

  cluster_name           = aws_eks_cluster.this.name
  fargate_profile_name   = "${var.cluster_name}-fargate"
  pod_execution_role_arn = aws_iam_role.fargate[0].arn
  subnet_ids             = aws_subnet.private[*].id

  selector {
    namespace = "event-ticketing"
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-fargate"
  })

  depends_on = [aws_eks_cluster.this]
}
