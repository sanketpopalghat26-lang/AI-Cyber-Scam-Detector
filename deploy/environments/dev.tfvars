# =============================================================================
# Development Environment Variables
# =============================================================================
environment = "development"
aws_region  = "us-east-1"

# Minimal resources for dev
vpc_cidr           = "10.1.0.0/16"
availability_zones = ["us-east-1a"]
private_subnets    = ["10.1.1.0/24"]
public_subnets     = ["10.1.101.0/24"]

# EKS node group settings
node_groups = {
  general = {
    instance_types = ["t3.small"]
    min_size       = 1
    max_size       = 2
    desired_size   = 1
    disk_size      = 20
  }
}

# RDS settings
db_instance_class = "db.t3.small"
db_allocated_storage = 20

# ElastiCache settings
cache_node_type = "cache.t3.small"
cache_num_nodes = 1
