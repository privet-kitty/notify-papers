
# S3 Bucket for duplicate detection
resource "aws_s3_bucket" "papers_bucket" {
  bucket = "${var.project_name}-papers-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "papers_bucket_versioning" {
  bucket = aws_s3_bucket.papers_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "papers_bucket_encryption" {
  bucket = aws_s3_bucket.papers_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.papers_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "${aws_s3_bucket.papers_bucket.arn}"
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/${var.llm_model}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "translate:TranslateText"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "paper_agent" {
  filename         = "../lambda-deployment-package.zip"
  source_code_hash = filebase64sha256("../lambda-deployment-package.zip")
  function_name    = "${var.project_name}-agent"
  role            = aws_iam_role.lambda_role.arn
  handler         = "src.report_papers.main.lambda_handler"
  runtime         = "python3.12"
  timeout         = 300
  memory_size     = 512

  environment {
    variables = {
      S3_PAPERS_BUCKET = aws_s3_bucket.papers_bucket.bucket
      EMAIL_RECIPIENT  = var.email_recipient
      RESEARCH_TOPICS  = join(",", var.research_topics)
      LLM_MODEL        = var.llm_model
      AWS_BEDROCK_REGION = var.aws_region
      TRANSLATE_TARGET_LANGUAGE = var.translate_target_language
      ARXIV_CATEGORIES = join(",", var.arxiv_categories)
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.lambda_logs,
  ]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-agent"
  retention_in_days = 14
}

# CloudWatch Event Rule (daily schedule)
resource "aws_cloudwatch_event_rule" "daily_schedule" {
  name                = "${var.project_name}-daily-schedule"
  description         = "Trigger paper agent daily"
  schedule_expression = "cron(0 9 * * ? *)"  # 9 AM UTC daily
}

# CloudWatch Event Target
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_schedule.name
  target_id = "TriggerLambda"
  arn       = aws_lambda_function.paper_agent.arn
}

# Lambda permission for CloudWatch Events
resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.paper_agent.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_schedule.arn
}

# SES Email Identity
resource "aws_ses_email_identity" "sender" {
  email = var.email_recipient
}
