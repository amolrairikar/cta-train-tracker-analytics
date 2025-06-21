"""Module for unit testing of the write_train_lines lambda handler function."""
import unittest
from unittest.mock import patch, MagicMock
import json

import botocore
import botocore.exceptions

from lambdas.write_train_lines.write_train_lines import get_sqs_queue_url, send_message_to_sqs


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