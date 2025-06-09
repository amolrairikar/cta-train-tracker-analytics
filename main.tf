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

module "dynamodb_table" {
  source            = "git::https://github.com/amolrairikar/aws-account-infrastructure.git//modules/dynamodb?ref=main"
  environment       = var.environment
  project           = var.project_name
  table_name        = "cta-train-tracker-location-data"
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
    },
    {
      name = "DestinationStation"
      type = "S"
    },
    {
      name = "NextStationName"
      type = "S"
    },
    {
      name = "PredictionGeneratedTime"
      type = "S"
    },
    {
      name = "PredictedArrivalTime"
      type = "S"
    },
    {
      name = "IsApproaching"
      type = "S"
    },
    {
      name = "IsDelayed"
      type = "S"
    }
  ]
  enable_ttl        = true
}