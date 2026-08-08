# =============================================================================
# Terraform Root Module — AI Cyber Scam Detector
# =============================================================================
terraform {
  required_version = ">= 1.8.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.2"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.14"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.55"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.38"
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

  backend "s3" {
    bucket = "scam-detector-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
    dynamodb_table = "scam-detector-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "AI-Cyber-Scam-Detector"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Platform-Team"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

module "vpc" {
  source = "./modules/aws-ecs"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  private_subnets    = var.private_subnets
  public_subnets     = var.public_subnets
}

module "eks" {
  source = "./modules/kubernetes"

  cluster_name    = "scam-detector-${var.environment}"
  cluster_version = "1.30"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids
  environment     = var.environment
  node_groups = {
    general = {
      instance_types = ["t3.medium", "t3.large"]
      min_size       = 2
      max_size       = 6
      desired_size   = 2
      disk_size      = 50
      labels = {
        role = "general"
      }
    }
    cpu-intensive = {
      instance_types = ["c6i.large", "c6i.xlarge"]
      min_size       = 1
      max_size       = 4
      desired_size   = 1
      disk_size      = 100
      labels = {
        role = "cpu-intensive"
      }
      taints = [
        {
          key    = "dedicated"
          value  = "cpu-intensive"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }
}

module "rds" {
  source = "./modules/aws-ecs"

  environment          = var.environment
  db_name              = "scamdb"
  db_username          = "scam_user"
  db_password          = random_password.db_password.result
  vpc_id               = module.vpc.vpc_id
  subnet_ids           = module.vpc.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
}

module "elasticache" {
  source = "./modules/aws-ecs"

  environment          = var.environment
  vpc_id               = module.vpc.vpc_id
  subnet_ids           = module.vpc.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  redis_password       = random_password.redis_password.result
}

module "ecr" {
  source = "./modules/aws-ecs"

  environment      = var.environment
  repository_names = ["scam-detector-backend", "scam-detector-frontend"]
}

module "scam-detector" {
  source = "../helm/scam-detector"

  backend = {
    secrets = {
      SECRET_KEY     = random_password.secret_key.result
      DATABASE_URL   = "postgresql://scam_user:${urlencode(random_password.db_password.result)}@${module.rds.endpoint}:5432/scamdb"
      REDIS_URL      = "redis://:${random_password.redis_password.result}@${module.elasticache.endpoint}:6379/0"
      REDIS_PASSWORD = random_password.redis_password.result
      CSRF_SECRET    = random_password.csrf_secret.result
    }
  }
}

resource "random_password" "secret_key" {
  length  = 64
  special = true
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "random_password" "redis_password" {
  length  = 32
  special = false
}

resource "random_password" "csrf_secret" {
  length  = 64
  special = true
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "private_subnets" {
  description = "Private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
}

output "elasticache_endpoint" {
  description = "ElastiCache endpoint"
  value       = module.elasticache.endpoint
}

output "ecr_repositories" {
  description = "ECR repository URLs"
  value       = module.ecr.repository_urls
}
