provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ProjectCode = var.project_name
      ManagedBy   = "terraform"
    }
  }
}

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}