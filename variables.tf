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

variable "aws_region_name" {
  description = "The AWS region where resources are deployed"
  type        = string
}

variable "cta_train_tracker_api_key" {
  description = "The API key for the CTA Train Tracker API"
  type        = string
}