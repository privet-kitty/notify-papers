# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
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
  description = "Amazon Bedrock LLM model to use for paper evaluation"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "iam_permissions_boundary" {
  description = "ARN of the IAM permissions boundary to attach to roles (optional)"
  type        = string
  default     = null
}