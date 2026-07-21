resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${local.name_prefix}-db-subnets" }
}

locals {
  db_backup_retention = (
    var.db_backup_retention_days != null
    ? var.db_backup_retention_days
    : (var.environment == "prod" ? 7 : 1)
  )
  db_deletion_protection = (
    var.db_deletion_protection != null
    ? var.db_deletion_protection
    : var.environment == "prod"
  )
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.db_instance_class
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Multi-AZ: synchronous standby in another AZ (failover ~1–2 min).
  # Toggle via db_multi_az; enabling on an existing instance triggers a brief outage window.
  multi_az            = var.db_multi_az
  publicly_accessible = false

  skip_final_snapshot       = var.environment != "prod"
  deletion_protection       = local.db_deletion_protection
  backup_retention_period   = local.db_backup_retention
  copy_tags_to_snapshot     = true
  final_snapshot_identifier = var.environment == "prod" ? "${local.name_prefix}-final" : null

  # Prefer weekday night UTC; adjust per region ops window if needed.
  backup_window      = "07:00-08:00"
  maintenance_window = "sun:08:00-sun:09:00"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name     = "${local.name_prefix}-postgres"
    MultiAZ  = tostring(var.db_multi_az)
  }
}

locals {
  database_url = format(
    "postgresql+psycopg2://%s:%s@%s:5432/%s",
    var.db_username,
    urlencode(random_password.db.result),
    aws_db_instance.main.address,
    var.db_name,
  )
}
