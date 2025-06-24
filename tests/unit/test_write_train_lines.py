"""Module for unit testing of the write_train_lines lambda handler function."""
import unittest
from unittest.mock import patch, MagicMock
import json
import os

import botocore
import botocore.exceptions

from lambdas.write_train_lines.write_train_lines import get_sqs_queue_url, send_message_to_sqs, lambda_handler


class TestGetQueueUrl(unittest.TestCase):
    """Unit tests for the get_sqs_queue_url method."""
    
    def test_get_sqs_queue_url_success(self):
        """Test successful retrieval of SQS queue URL."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_sqs_client.get_queue_url.return_value = {
                'QueueUrl': 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue'
            }
            mock_boto_client.return_value = mock_sqs_client

            queue_url = get_sqs_queue_url(mock_sqs_client, 'test-sqs-queue')

            self.assertEqual(queue_url, 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue')
            mock_sqs_client.get_queue_url.assert_called_once_with(QueueName='test-sqs-queue')

    def test_get_sqs_queue_url_queue_does_not_exist(self):
        """Test handling of QueueDoesNotExist exception."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_sqs_client.get_queue_url.side_effect = botocore.exceptions.ClientError(
                {'Error': {'Code': 'QueueDoesNotExist', 'Message': 'Queue does not exist'}},
                'GetQueueUrl'
            )
            mock_boto_client.return_value = mock_sqs_client

            with self.assertRaises(botocore.exceptions.ClientError):
                get_sqs_queue_url(mock_sqs_client, 'non-existent-queue')

    def test_retry_get_sqs_queue_url(self):
        """Test retry logic for get_sqs_queue_url on ClientError."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_sqs_client.get_queue_url.side_effect = [
                botocore.exceptions.ClientError(
                    {'Error': {'Code': 'RequestThrottled', 'Message': 'Request was throttled'}},
                    'GetQueueUrl'
                ),
                {
                    'QueueUrl': 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue'
                }
            ]
            mock_boto_client.return_value = mock_sqs_client

            queue_url = get_sqs_queue_url(mock_sqs_client, 'test-sqs-queue')

            self.assertEqual(queue_url, 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue')
            self.assertEqual(mock_sqs_client.get_queue_url.call_count, 2)


class TestSendMessageToSqs(unittest.TestCase):
    """Unit tests for the send_message_to_sqs method."""
    
    def test_send_message_to_sqs_success(self):
        """Test successful sending of message to SQS."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_boto_client.return_value = mock_sqs_client
            queue_url = 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue'
            message_body = {'key': 'value'}

            send_message_to_sqs(
                sqs_client=mock_sqs_client,
                queue_url=queue_url,
                message_body=message_body
            )

            mock_sqs_client.send_message.assert_called_once_with(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )

    def test_send_message_to_sqs_client_error(self):
        """Test handling of ClientError when sending message to SQS."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_sqs_client.send_message.side_effect = botocore.exceptions.ClientError(
                {'Error': {'Code': 'KmsAccessDenied', 'Message': 'KmsAccessDenied'}},
                'SendMessage'
            )
            mock_boto_client.return_value = mock_sqs_client

            queue_url = 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue'
            message_body = {'key': 'value'}

            with self.assertRaises(botocore.exceptions.ClientError):
                send_message_to_sqs(mock_sqs_client, queue_url, message_body)
    
    def test_retry_send_message_to_sqs(self):
        """Test retry logic for send_message_to_sqs on ClientError."""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs_client = MagicMock()
            mock_sqs_client.send_message.side_effect = [
                botocore.exceptions.ClientError(
                    {'Error': {'Code': 'RequestThrottled', 'Message': 'Request was throttled'}},
                    'SendMessage'
                ),
                None
            ]
            mock_boto_client.return_value = mock_sqs_client

            queue_url = 'https://sqs.us-east-2.amazonaws.com/123456789012/test-sqs-queue'
            message_body = {'key': 'value'}

            send_message_to_sqs(mock_sqs_client, queue_url, message_body)

            self.assertEqual(mock_sqs_client.send_message.call_count, 2)


class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'


class TestLambdaHandler(unittest.TestCase):
    """Class for testing lambda_handler method."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.mock_event = {'event-name': 'test-event'}
        self.env_patcher = patch.dict(
            os.environ,
            {
                'SQS_QUEUE_NAME': 'test-queue',
                'REGION_NAME': 'us-east-2'
            }
        )
        self.env_patcher.start()

    def tearDown(self):
        """Stop all patches after each test."""
        self.env_patcher.stop()

    @patch('lambdas.write_train_lines.write_train_lines.get_sqs_queue_url')
    @patch('lambdas.write_train_lines.write_train_lines.send_message_to_sqs')
    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_lambda_handler_success(self, mock_boto_client, mock_send_message, mock_get_queue_url):
        """Tests successful (happy path) lambda_handler invocation."""
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_send_message.return_value = None
        mock_get_queue_url.return_value = 'test-queue-url'

        response = lambda_handler(event=self.mock_event, context=MockLambdaContext())

        self.assertEqual(
            response,
            {
                'statusCode': 200,
                'body': 'Processed all train lines'
            }
        )
        self.assertEqual(mock_send_message.call_count, 7)

    def test_missing_queue_name_env_variable(self):
        """Tests KeyError is raised if SQS_QUEUE_NAME env variable is missing."""
        del os.environ['SQS_QUEUE_NAME']

        with self.assertRaises(KeyError):
            lambda_handler(event=self.mock_event, context=MockLambdaContext())

    def test_missing_region_name_env_variable(self):
        """Tests KeyError is raised if REGION_NAME env variable is missing."""
        del os.environ['REGION_NAME']

        with self.assertRaises(KeyError):
            lambda_handler(event=self.mock_event, context=MockLambdaContext())

    @patch('lambdas.write_train_lines.write_train_lines.get_sqs_queue_url')
    @patch('lambdas.write_train_lines.write_train_lines.send_message_to_sqs')
    @patch('lambdas.write_train_lines.write_train_lines.boto3.client')
    @patch('lambdas.write_train_lines.write_train_lines.cta_train_lines')
    def test_lambda_handler_no_train_lines(self, mock_train_lines, mock_boto_client, mock_send_message, mock_get_queue_url):
        """Tests lambda_handler if no train lines to write."""
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_send_message.return_value = None
        mock_get_queue_url.return_value = 'test-queue-url'
        mock_train_lines.return_value = {}

        response = lambda_handler(event=self.mock_event, context=MockLambdaContext())

        self.assertEqual(
            response,
            {
                'statusCode': 200,
                'body': 'Processed all train lines'
            }
        )
        self.assertEqual(mock_send_message.call_count, 0)