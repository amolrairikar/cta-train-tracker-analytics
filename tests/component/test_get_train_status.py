"""Module for component testing of the get_train_status lambda handler function."""
import unittest
from unittest.mock import patch
import os

import boto3
import botocore
import botocore.client
from moto import mock_aws

from lambdas.get_train_status.get_train_status import lambda_handler
from tests.helper_files.mock_train_location_response import MOCK_TRAIN_LOCATION_RESPONSE


class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'


class TestGetTrainStatus(unittest.TestCase):
    """Class for testing get_train_status Lambda function."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.mock_event = {
            "Records": [
                {
                    "messageId": "id123",
                    "receiptHandle": "this_is_a_random_string",
                    "body": "{\"train_line_abbrev\": \"P\", \"train_line\": \"Purple\"}",
                    "attributes": {
                        "ApproximateReceiveCount": "1",
                        "AWSTraceHeader": "random_information",
                        "SentTimestamp": "12345678910",
                        "SenderId": "sender_id",
                        "ApproximateFirstReceiveTimestamp": "13345678910"
                    },
                    "messageAttributes": {},
                    "md5OfBody": "this_is_another_random_string",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-2:123456789:sqs-queue",
                    "awsRegion": "us-east-2"
                }
            ]
        }
        self.env_patcher = patch.dict(
            os.environ,
            {
                'S3_BUCKET_NAME': 'test-bucket'
            }
        )
        self.env_patcher.start()

    def tearDown(self):
        """Stop all patches after each test."""
        self.env_patcher.stop()

    @mock_aws
    @patch('lambdas.get_train_status.get_train_status.get_train_locations')
    def test_lambda_handler_success(self, mock_train_locations):
        """Tests successful (happy path) lambda_handler invocation."""
        s3 = boto3.client('s3')
        s3.create_bucket(
            Bucket='test-bucket',
            CreateBucketConfiguration={
                'LocationConstraint': 'us-east-2'
            }
        )
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_RESPONSE

        response = lambda_handler(
            event=self.mock_event,
            context=MockLambdaContext()
        )

        self.assertEqual(
            response,
            {
                'statusCode': 200,
                'body': 'Execution successful'
            }
        )

    @mock_aws
    @patch('lambdas.get_train_status.get_train_status.get_train_locations')
    def test_lambda_handler_missing_s3_bucket(self, mock_train_locations):
        """Tests the lambda_handler invocation if the target S3 bucket does not exist."""
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_RESPONSE

        with self.assertRaises(botocore.client.ClientError):
            lambda_handler(
                event=self.mock_event,
                context=MockLambdaContext()
            )
