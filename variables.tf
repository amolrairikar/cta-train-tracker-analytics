variable "infra_role_arn" {
  description = "The ARN for the role assumed by the Terraform user"
  type        = string
}

variable "environment" {
  description = "The deployment environment (QA or PROD)"
  type        = string
}

variable "project_name" {
  description = "The name of the project (to be used in tags)"
  type        = string
}