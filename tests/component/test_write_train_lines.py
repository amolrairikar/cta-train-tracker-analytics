"""Module for component testing of the write_train_lines lambda handler function."""
import unittest
from unittest.mock import patch
import os

import boto3
from moto import mock_aws

from lambdas.write_train_lines.write_train_lines import lambda_handler


class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'


class TestWriteTrainLines(unittest.TestCase):
    """Class for testing write_train_lines Lambda function."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.mock_event = {
            'eventType': 'test-event'
        }
        self.env_patcher = patch.dict(
            os.environ,
            {
                'SQS_QUEUE_NAME': 'test-sqs-queue',
                'REGION_NAME': 'us-east-2'
            }
        )
        self.env_patcher.start()

    def tearDown(self):
        """Stop all patches after each test."""
        self.env_patcher.stop()

    @mock_aws
    def test_lambda_handler_success(self):
        """Test successful execution of the lambda_handler function."""
        sqs = boto3.client('sqs', region_name='us-east-2')
        sqs.create_queue(QueueName='test-sqs-queue')

        lambda_handler(self.mock_event, MockLambdaContext())

        queue_url = sqs.get_queue_url(QueueName='test-sqs-queue')['QueueUrl']
        messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        self.assertIn('Messages', messages)
        self.assertEqual(len(messages['Messages']), 7)

    @mock_aws
    def test_missing_sqs_queue_url(self):
        """Test handling of missing SQS queue URL in environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                lambda_handler(self.mock_event, MockLambdaContext())
