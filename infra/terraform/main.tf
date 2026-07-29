provider "aws" {
  region = var.aws_region
}

provider "random" {
  # no config needed
}

# Terraform state is local by default for portfolio simplicity.
# For team use, migrate to S3 + DynamoDB:
#   backend "s3" {
#     bucket         = "event-ticketing-tfstate"
#     key            = "terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "event-ticketing-tfstate-lock"
#     encrypt        = true
#   }
