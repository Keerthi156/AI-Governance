resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name_prefix}/app"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = { Name = "${local.name_prefix}-app-secrets" }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL      = local.database_url
    JWT_SECRET_KEY    = var.jwt_secret_key
    OPENAI_API_KEY    = var.openai_api_key
    ANTHROPIC_API_KEY = var.anthropic_api_key
    GOOGLE_API_KEY    = var.google_api_key
    GROQ_API_KEY      = var.groq_api_key
  })
}
