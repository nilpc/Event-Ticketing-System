resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.cluster_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-db-subnet-group"
  })
}

resource "aws_db_instance" "this" {
  identifier = "${var.cluster_name}-db"

  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 50
  storage_encrypted     = true

  multi_az               = false
  publicly_accessible    = false
  skip_final_snapshot    = true
  deletion_protection    = false

  db_subnet_group_name = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:06:00"

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-db"
  })
}

resource "aws_ssm_parameter" "db_url" {
  name  = "/event-ticketing/DATABASE_URL"
  type  = "SecureString"
  value = "postgresql+asyncpg://${var.db_username}:${urlencode(random_password.db.result)}@${aws_db_instance.this.endpoint}/${var.db_name}"

  tags = var.tags
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/event-ticketing/DB_PASSWORD"
  type  = "SecureString"
  value = random_password.db.result

  tags = var.tags
}
