"""Module for unit testing of the get_train_status lambda handler function."""
import unittest
from unittest.mock import patch, MagicMock
import os
import json
import datetime
import zoneinfo

import botocore
import botocore.exceptions
import requests

from lambdas.get_train_status.get_train_status import get_train_locations, write_train_location_data, lambda_handler
from tests.helper_files.mock_train_location_response import MOCK_TRAIN_LOCATION_RESPONSE
from tests.helper_files.mock_train_location_response_no_trains import MOCK_TRAIN_LOCATION_NO_TRAINS_RESPONSE
from tests.helper_files.mock_train_location_response_no_route_object import MOCK_TRAIN_LOCATION_NO_ROUTE_OBJECT


class TestGetTrainLocations(unittest.TestCase):
    """Class for testing get_train_locations method."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.env_patcher = patch.dict(
            os.environ,
            {
                'API_KEY': 'api-key'
            }
        )
        self.env_patcher.start()

    def tearDown(self):
        """Stop all patches after each test."""
        self.env_patcher.stop()

    @patch('lambdas.get_train_status.get_train_status.requests.get')
    def test_get_train_locations_success(self, mock_get):
        """Tests a successful API request to the Train Locations CTA API endpoint."""
        mock_json = MOCK_TRAIN_LOCATION_RESPONSE
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_json
        mock_get.return_value = mock_response

        get_train_locations(train_line_abbrev='P')

        mock_get.assert_called_once_with(
            url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
            params = {
                'rt': 'P',
                'key': 'api-key',
                'outputType': 'JSON'
            }
        )

    @patch('lambdas.get_train_status.get_train_status.requests.get')
    def test_get_train_locations_failure(self, mock_get):
        """Tests when an error occurs with the API request to the Train Locations CTA API endpoint."""
        response_mock = MagicMock()
        response_mock.status_code = 400
        http_error = requests.exceptions.HTTPError(
            '400 Client Error: Bad Request for url'
        )
        http_error.response = response_mock
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            get_train_locations(train_line_abbrev='P')

        mock_get.assert_called_once_with(
            url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
            params = {
                'rt': 'P',
                'key': 'api-key',
                'outputType': 'JSON'
            }
        )

    @patch('lambdas.get_train_status.get_train_status.requests.get')
    def test_get_train_locations_retry(self, mock_get):
        """Tests the API request to the Train Locations CTA API endpoint gets retried for the appropriate HTTP codes."""
        response_mock = MagicMock()
        response_mock.status_code = 429
        http_error = requests.exceptions.HTTPError(
            '429 Client Error: Too many requests'
        )
        http_error.response = response_mock
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            get_train_locations(train_line_abbrev='P')

        mock_get.assert_called_with(
            url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
            params = {
                'rt': 'P',
                'key': 'api-key',
                'outputType': 'JSON'
            }
        )
        self.assertEqual(mock_get.call_count, 3)


class TestWriteTrainLocationData(unittest.TestCase):
    """Class for testing write_train_location_data method."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.env_patcher = patch.dict(
            os.environ,
            {
                'S3_BUCKET_NAME': 'test-bucket'
            }
        )
        self.output_data = [{'foo': 'bar'}]
        self.env_patcher.start()

    def tearDown(self):
        """Stop all patches after each test."""
        self.env_patcher.stop()

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_success(self, mock_boto_client):
        """Tests a successful write to S3 of train location data."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        write_train_location_data(output_data=self.output_data)

        # Using this method to check call args to avoid mocking datetime.datetime.now
        _, kwargs = mock_s3.put_object.call_args
        self.assertEqual(kwargs['Bucket'], 'test-bucket')
        self.assertTrue(kwargs['Key'].startswith('raw/'))
        self.assertTrue(kwargs['Key'].endswith('.json'))
        self.assertIn('"foo": "bar"', kwargs['Body'])
        self.assertEqual(kwargs['ContentType'], 'application/json')

    def test_write_train_location_data_missing_env_variable(self):
        """Tests a non-retryable boto3 exception with writing data to S3."""
        del os.environ['S3_BUCKET_NAME']

        with self.assertRaises(KeyError):
            write_train_location_data(output_data=self.output_data)

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_boto3_error(self, mock_boto_client):
        """Tests a non-retryable boto3 exception with writing data to S3."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = botocore.exceptions.ClientError(
            error_response={'Error': {'Code': 'AccessDenied'}},
            operation_name='PutObject'
        )
        mock_boto_client.return_value = mock_s3
        with self.assertRaises(botocore.exceptions.ClientError):
            write_train_location_data(output_data=self.output_data)

        # Using this method to check call args to avoid mocking datetime.datetime.now
        _, kwargs = mock_s3.put_object.call_args
        self.assertEqual(kwargs['Bucket'], 'test-bucket')
        self.assertTrue(kwargs['Key'].startswith('raw/'))
        self.assertTrue(kwargs['Key'].endswith('.json'))
        self.assertIn('"foo": "bar"', kwargs['Body'])
        self.assertEqual(kwargs['ContentType'], 'application/json')

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_boto3_retryable_error(self, mock_boto_client):
        """Tests a retryable boto3 exception with writing data to S3."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = botocore.exceptions.ClientError(
            error_response={'Error': {'Code': 'InternalServerError'}},
            operation_name='PutObject'
        )
        mock_boto_client.return_value = mock_s3
        with self.assertRaises(botocore.exceptions.ClientError):
            write_train_location_data(output_data=self.output_data)

        # Using this method to check call args to avoid mocking datetime.datetime.now
        _, kwargs = mock_s3.put_object.call_args
        self.assertEqual(kwargs['Bucket'], 'test-bucket')
        self.assertTrue(kwargs['Key'].startswith('raw/'))
        self.assertTrue(kwargs['Key'].endswith('.json'))
        self.assertIn('"foo": "bar"', kwargs['Body'])
        self.assertEqual(kwargs['ContentType'], 'application/json')

        self.assertEqual(mock_s3.put_object.call_count, 3)


class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'


class TestLambdaHandler(unittest.TestCase):
    """Class for testing lambda_handler module."""

    def setUp(self):
        """Patch common dependencies before each test."""
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
        self.today_date = datetime.datetime.now(zoneinfo.ZoneInfo('America/Chicago')).date().strftime('%Y-%m-%d')

    @patch('lambdas.get_train_status.get_train_status.get_train_locations')
    @patch('lambdas.get_train_status.get_train_status.write_train_location_data')
    def test_lambda_handler_success(self, mock_train_locations_write, mock_train_locations):
        """Tests successful (happy path) lambda_handler invocation."""
        mock_train_locations_write.return_value = None
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_RESPONSE
        expected_output_data = [
            {
                'TrainId': f'{self.today_date}#Purple#110#5',
                'PredictionGeneratedTimestamp': '2025-06-20T12:42:56',
                'DestinationStation': 'Forest Park',
                'NextStation': 'Belmont',
                'NextStationArrivalTime': '2025-06-20T12:43:56',
                'ApproachingStation': '1',
                'TrainDelayed': '0'
            }
        ]

        response = lambda_handler(
            event=self.mock_event,
            context=MockLambdaContext()
        )
        _, kwargs = mock_train_locations_write.call_args

        self.assertEqual(
            response,
            {
                'statusCode': 200,
                'body': 'Execution successful'
            }
        )
        assert expected_output_data == kwargs['output_data']

    def test_lambda_handler_missing_train_abbrev(self):
        """Tests lambda handler invocation with missing train_abbrev parameter in SQS message body."""
        mock_event = {
            "Records": [
                {
                    "messageId": "id123",
                    "receiptHandle": "this_is_a_random_string",
                    "body": "{\"train_line\": \"Purple\"}",
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

        with self.assertRaises(ValueError):
            lambda_handler(
                event=mock_event,
                context=MockLambdaContext()
            )

    @patch('lambdas.get_train_status.get_train_status.get_train_locations')
    def test_lambda_handler_no_trains(self, mock_train_locations):
        """Tests lambda_handler invocation if no trains are running."""
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_NO_TRAINS_RESPONSE

        response = lambda_handler(
            event=self.mock_event,
            context=MockLambdaContext()
        )

        self.assertEqual(
            response,
            {
                'statusCode': 204,
                'body': 'No records written due to no trains running'
            }
        )

    @patch('lambdas.get_train_status.get_train_status.get_train_locations')
    def test_lambda_handler_no_route_object(self, mock_train_locations):
        """Tests lambda_handler invocation if no route object is found in the locations response."""
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_NO_ROUTE_OBJECT

        with self.assertRaises(KeyError):
            lambda_handler(
                event=self.mock_event,
                context=MockLambdaContext()
            )
