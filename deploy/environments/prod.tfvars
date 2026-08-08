# =============================================================================
# Production Environment Variables
# =============================================================================
environment = "production"
aws_region  = "us-east-1"

# Full HA resources for production
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
private_subnets    = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnets     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

# EKS node group settings
node_groups = {
  general = {
    instance_types = ["t3.medium", "t3.large"]
    min_size       = 3
    max_size       = 6
    desired_size   = 3
    disk_size      = 50
  }
  cpu-intensive = {
    instance_types = ["c6i.large", "c6i.xlarge"]
    min_size       = 2
    max_size       = 6
    desired_size   = 2
    disk_size      = 100
  }
}

# RDS settings
db_instance_class = "db.r6g.large"
db_allocated_storage = 100
db_multi_az = true
db_backup_retention_period = 30
db_deletion_protection = true

# ElastiCache settings
cache_node_type = "cache.r6g.large"
cache_num_nodes = 3
cache_multi_az_enabled = true

# Monitoring
enable_monitoring = true

# Backup
enable_backup = true
backup_retention_days = 30

# Security
enable_waf = true
enable_shield_advanced = true
enable_guardduty = true
enable_security_hub = true

# Observability
enable_cloudwatch_dashboard = true
enable_container_insights = true
enable_prometheus_monitoring = true
