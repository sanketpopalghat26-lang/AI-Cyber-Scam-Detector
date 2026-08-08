# =============================================================================
# Staging Environment Variables
# =============================================================================
environment = "staging"
aws_region  = "us-east-1"

# Moderate resources for staging
vpc_cidr           = "10.2.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]
private_subnets    = ["10.2.1.0/24", "10.2.2.0/24"]
public_subnets     = ["10.2.101.0/24", "10.2.102.0/24"]

# EKS node group settings
node_groups = {
  general = {
    instance_types = ["t3.medium"]
    min_size       = 2
    max_size       = 4
    desired_size   = 2
    disk_size      = 50
  }
}

# RDS settings
db_instance_class = "db.t3.medium"
db_allocated_storage = 50

# ElastiCache settings
cache_node_type = "cache.t3.medium"
cache_num_nodes = 2
