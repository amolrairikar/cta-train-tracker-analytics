terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-east-2"
  assume_role {
    role_arn     = var.infra_role_arn
    session_name = "terraform-session"
  }
}

module "application_dynamodb_table" {
  source            = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/dynamodb?ref=main"
  environment       = var.environment
  project           = var.project_name
  table_name        = "cta-train-tracker-location-application-data"
  hash_key          = "TrainId"
  range_key         = "UpdatedTimestamp"
  attributes        = [
    {
      name = "TrainId"
      type = "S"
    },
    {
      name = "UpdatedTimestamp"
      type = "S"
    }
  ]
  enable_ttl        = true
}

module "sqs_queue" {
  source                     = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/sqs-topic?ref=main"
  queue_name                 = "cta-train-tracker-analytics-lambda-trigger-queue"
  visibility_timeout_seconds = 10
  project                    = var.project_name
  environment                = var.environment
}

data "aws_iam_policy_document" "lambda_trust_relationship_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "lambda_get_cta_train_status_execution_role_inline_policy_document" {
  statement {
    effect    = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [
      module.sqs_queue.queue_arn
    ]
  }
  statement {
    effect    = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [
      var.sns_topic_arn
    ]
  }
  statement {
    effect    = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "*"
    ]
  }
}

module "lambda_get_cta_train_status_execution_role" {
  source                    = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/iam-role?ref=main"
  role_name                 = "cta-lambda-get-cta-train-status-execution-role"
  trust_relationship_policy = data.aws_iam_policy_document.lambda_trust_relationship_policy.json
  inline_policy             = data.aws_iam_policy_document.lambda_get_cta_train_status_execution_role_inline_policy_document.json
  inline_policy_description = "Inline policy for CTA train analytics train status Lambda function execution role"
  environment               = var.environment
  project                   = var.project_name
}

module "cta_get_train_status_lambda" {
  source                         = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/lambda?ref=main"
  environment                    = var.environment
  project                        = var.project_name
  lambda_name                    = "cta-get-train-status-lambda"
  lambda_description             = "Lambda function to get current status of CTA trains from the CTA Train Tracker API"
  lambda_filename                = "get_train_status.zip"
  lambda_handler                 = "get_train_status.lambda_handler"
  lambda_memory_size             = "256"
  lambda_runtime                 = "python3.12"
  lambda_timeout                 = 30
  lambda_execution_role_arn      = module.lambda_get_cta_train_status_execution_role.role_arn
  sns_topic_arn                  = var.sns_topic_arn
    lambda_environment_variables = {
      API_KEY = var.cta_train_tracker_api_key
  }
}

module "sqs_lambda_trigger" {
  source              = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/sqs-lambda-trigger?ref=main"
  sqs_queue_arn       = module.sqs_queue.queue_arn
  lambda_function_arn = module.cta_get_train_status_lambda.lambda_arn
  trigger_enabled     = true
  batch_size          = 1
}