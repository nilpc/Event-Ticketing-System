variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "event-ticketing"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "event_ticketing"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "etadmin"
}

variable "eks_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.30"
}

variable "on_demand_instance_types" {
  description = "Instance types for on-demand node group"
  type        = list(string)
  default     = ["t3.medium", "t3.small"]
}

variable "on_demand_min_size" {
  description = "Minimum size of on-demand node group"
  type        = number
  default     = 1
}

variable "on_demand_max_size" {
  description = "Maximum size of on-demand node group"
  type        = number
  default     = 4
}

variable "on_demand_desired_size" {
  description = "Desired size of on-demand node group"
  type        = number
  default     = 2
}

variable "domain_name" {
  description = "Custom domain for HTTPS (optional). If empty, HTTP-only ALB."
  type        = string
  default     = ""
}

variable "fargate_enabled" {
  description = "Enable Fargate profile for event-ticketing namespace (zero node management)"
  type        = bool
  default     = false
}

variable "redis_password" {
  description = "Password for self-hosted Redis. Auto-generated if empty."
  type        = string
  default     = ""
  sensitive   = true
}

variable "waf_action" {
  description = "WAF default rule action: 'count' (observe only) or 'block' (enforce). Start with 'count', switch to 'block' after validating in CloudWatch."
  type        = string
  default     = "count"
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "event-ticketing"
    ManagedBy   = "terraform"
    Environment = "production"
  }
}
