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
  }

  # Migrate from local to S3 after first apply:
  #   terraform init -migrate-state -backend-config="bucket=$(terraform output -raw tfstate_bucket)" -backend-config="dynamodb_table=$(terraform output -raw tfstate_lock_table)"
  # backend "s3" {
  #   bucket         = "event-ticketing-tfstate"
  #   key            = "terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "event-ticketing-tfstate-lock"
  #   encrypt        = true
  # }
}
