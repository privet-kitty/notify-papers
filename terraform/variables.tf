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
  description = "Email recipient for notifications"
  type        = string
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