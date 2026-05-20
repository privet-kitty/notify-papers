# Variables
variable "aws_region" {
  description = "AWS region for infrastructure resources"
  type        = string
  default     = "us-east-1"
}

variable "aws_bedrock_region" {
  description = "AWS region for Amazon Bedrock (defaults to aws_region if not set; set this when the desired Bedrock model/inference profile is not available in aws_region)."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "report-papers"
}

variable "email_recipient" {
  description = "Email recipient for notifications (optional if teams_webhook_url is set)"
  type        = string
  default     = null
}

variable "teams_webhook_url" {
  description = "Microsoft Teams webhook URL for notifications (optional if email_recipient is set)"
  type        = string
  default     = null
  sensitive   = true
}

variable "translate_target_language" {
  description = "Target language for translation (ISO 639-1 code, e.g., 'ja', 'en', 'es'). Use 'en' to disable translation."
  type        = string
  default     = "en"
}

variable "research_topics" {
  description = "Research topics to search for"
  type        = list(string)
}


variable "arxiv_categories" {
  description = "ArXiv categories to search within (e.g., ['econ.EM', 'cs.LG'])"
  type        = list(string)
}

variable "llm_model" {
  description = "Amazon Bedrock inference profile ID for paper evaluation (Claude 4.x models require an inference profile, not a bare foundation-model ID)."
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "iam_permissions_boundary" {
  description = "ARN of the IAM permissions boundary to attach to roles (optional)"
  type        = string
  default     = null
}

variable "schedule_expression" {
  description = "CloudWatch Events schedule expression (cron or rate)"
  type        = string
  default     = "cron(0 9 * * ? *)"  # 9 AM UTC daily
}