resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.eks_version
  role_arn = aws_iam_role.cluster.arn

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

resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name   = "vpc-cni"
  addon_version = "v1.18.3-eksbuild.1"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name   = "coredns"
  addon_version = "v1.11.3-eksbuild.1"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name   = "kube-proxy"
  addon_version = "v1.30.3-eksbuild.3"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name   = "aws-ebs-csi-driver"
  addon_version = "v1.35.0-eksbuild.1"

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_node_group" "on_demand" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-on-demand"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.private[*].id

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
    "node-type"    = "on-demand"
    "capacity-type" = "on-demand"
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-on-demand"
  })

  depends_on = [aws_eks_cluster.this]
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.private[*].id

  instance_types = var.spot_instance_types
  capacity_type  = "SPOT"

  scaling_config {
    desired_size = var.spot_desired_size
    min_size     = var.spot_min_size
    max_size     = var.spot_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "node-type"    = "spot"
    "capacity-type" = "spot"
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-spot"
  })

  depends_on = [aws_eks_cluster.this]
}
