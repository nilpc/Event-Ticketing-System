terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Migrate from local to S3 after first apply:
  #   terraform init -migrate-state -backend-config="bucket=$(terraform output -raw tfstate_bucket)" -backend-config="dynamodb_table=$(terraform output -raw tfstate_lock_table)"
  # backend "s3" {
  #   bucket         = aws_s3_bucket.tfstate.id  # dynamic — use output
  #   key            = "terraform.tfstate"
  #   region         = var.aws_region
  #   dynamodb_table = aws_dynamodb_table.tfstate_lock.name
  #   encrypt        = true
  # }
}
