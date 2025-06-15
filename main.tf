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

data "aws_caller_identity" "current" {}

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

module "eventbridge_scheduler" {
  source               = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/eventbridge-scheduler?ref=main"
  eventbridge_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/eventbridge-role"
  lambda_arn           = module.cta_write_train_lines_lambda.lambda_arn
  schedule_frequency   = "cron(* * * * ? *)"
  schedule_timezone    = "America/Chicago"
  schedule_state       = "ENABLED"
  scheduler_name       = "cta-write-train-lines-lambda-trigger"
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

data "aws_iam_policy_document" "lambda_write_train_lines_execution_role_inline_policy_document" {
  statement {
    effect    = "Allow"
    actions = [
      "sqs:SendMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ]
    resources = [
      "arn:aws:sqs:${var.aws_region_name}:${data.aws_caller_identity.current.account_id}:cta-train-tracker-analytics-lambda-trigger-queue"
    ]
  }
  statement {
    effect    = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [
      "arn:aws:sns:${var.aws_region_name}:${data.aws_caller_identity.current.account_id}:lambda-failure-notification-topic"
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

module "lambda_write_train_lines_role" {
  source                    = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/iam-role?ref=main"
  role_name                 = "cta-write-train-lines-lambda-execution-role"
  trust_relationship_policy = data.aws_iam_policy_document.lambda_trust_relationship_policy.json
  inline_policy             = data.aws_iam_policy_document.lambda_write_train_lines_execution_role_inline_policy_document.json
  inline_policy_description = "Inline policy for CTA Train Analytics cta-write-train-lines Lambda execution role"
  environment               = var.environment
  project                   = var.project_name
}

data "aws_lambda_layer_version" "latest_retry_api" {
  layer_name = "retry_api_exceptions"
}

data aws_s3_object "write_train_lines_zip" {
  bucket = "lambda-source-code-${data.aws_caller_identity.current.account_id}-bucket"
  key    = "cta_write_train_lines.zip"
}

module "cta_write_train_lines_lambda" {
  source                         = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/lambda?ref=main"
  environment                    = var.environment
  project                        = var.project_name
  lambda_name                    = "cta-write-train-lines"
  lambda_description             = "Lambda function to write CTA train lines each minute to SQS queue"
  lambda_handler                 = "write_train_lines.lambda_handler"
  lambda_memory_size             = "256"
  lambda_runtime                 = "python3.12"
  lambda_timeout                 = 30
  lambda_execution_role_arn      = module.lambda_write_train_lines_role.role_arn
  s3_bucket_name                 = "lambda-source-code-${data.aws_caller_identity.current.account_id}-bucket"
  s3_object_key                  = "cta_write_train_lines.zip"
  s3_object_version              = data.aws_s3_object.write_train_lines_zip.version_id
  lambda_layers                  = [data.aws_lambda_layer_version.latest_retry_api.arn]
  sns_topic_arn                  = "arn:aws:sns:${var.aws_region_name}:${data.aws_caller_identity.current.account_id}:lambda-failure-notification-topic"
    lambda_environment_variables = {
      SQS_QUEUE_NAME = "cta-train-tracker-analytics-lambda-trigger-queue"
      REGION_NAME     = var.aws_region_name
  }
}

module "sqs_queue" {
  source                     = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/sqs-topic?ref=main"
  queue_name                 = "cta-trigger-get-train-status"
  visibility_timeout_seconds = 35
  project                    = var.project_name
  environment                = var.environment
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
      "arn:aws:sns:${var.aws_region_name}:${data.aws_caller_identity.current.account_id}:lambda-failure-notification-topic"
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

data aws_s3_object "get_train_status_zip" {
  bucket = "lambda-source-code-${data.aws_caller_identity.current.account_id}-bucket"
  key    = "cta_get_train_status.zip"
}

module "cta_get_train_status_lambda" {
  source                         = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/lambda?ref=main"
  environment                    = var.environment
  project                        = var.project_name
  lambda_name                    = "cta-get-train-status"
  lambda_description             = "Lambda function to get current status of CTA trains from the CTA Train Tracker API"
  lambda_handler                 = "get_train_status.lambda_handler"
  lambda_memory_size             = "256"
  lambda_runtime                 = "python3.12"
  lambda_timeout                 = 30
  lambda_execution_role_arn      = module.lambda_get_cta_train_status_execution_role.role_arn
  s3_bucket_name                 = "lambda-source-code-${data.aws_caller_identity.current.account_id}-bucket"
  s3_object_key                  = "cta_get_train_status.zip"
  s3_object_version              = data.aws_s3_object.get_train_status_zip.version_id
  sns_topic_arn                  = "arn:aws:sns:${var.aws_region_name}:${data.aws_caller_identity.current.account_id}:lambda-failure-notification-topic"
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