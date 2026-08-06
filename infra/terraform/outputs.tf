output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.this.name
}
output "cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = aws_eks_cluster.this.endpoint
}
output "cluster_ca_certificate" {
  description = "EKS cluster CA certificate (base64)"
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}
output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (hostname:port)"
  value       = aws_db_instance.this.endpoint
  sensitive   = true
}
output "rds_db_name" {
  description = "PostgreSQL database name"
  value       = aws_db_instance.this.db_name
}
output "rds_username" {
  description = "PostgreSQL master username"
  value       = aws_db_instance.this.username
  sensitive   = true
}
output "db_url_ssm_arn" {
  description = "SSM parameter ARN for DATABASE_URL"
  value       = aws_ssm_parameter.db_url.arn
}
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.this.id
}
output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}
output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}
output "nat_gateway_ip" {
  description = "NAT Gateway Elastic IP"
  value       = aws_eip.nat.public_ip
}
output "node_group_name" {
  description = "On-demand node group name"
  value       = aws_eks_node_group.on_demand.node_group_name
}
output "tfstate_bucket" {
  description = "S3 bucket name for Terraform state"
  value       = aws_s3_bucket.tfstate.id
}
output "tfstate_lock_table" {
  description = "DynamoDB table name for Terraform state locking"
  value       = aws_dynamodb_table.tfstate_lock.id
}
output "waf_acl_arn" {
  description = "WAFv2 Web ACL ARN (for ALB ingress annotation)"
  value       = aws_wafv2_web_acl.this.arn
}
output "lb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller (for IRSA)"
  value       = aws_iam_role.lb_controller.arn
}
output "eso_role_arn" {
  description = "IAM role ARN for External Secrets Operator (for IRSA)"
  value       = aws_iam_role.eso.arn
}
output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler (for IRSA)"
  value       = aws_iam_role.cluster_autoscaler.arn
}
