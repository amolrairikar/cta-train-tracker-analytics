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

from lambdas.get_train_status.get_train_status import get_train_locations, dictionary_to_firehose_record, \
    write_train_location_data, lambda_handler
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


class TestDictionaryToFirehoseRecord(unittest.TestCase):
    """Class for testing dictionary_to_firehose_records method."""

    def test_basic_dict(self):
        """Tests converting a basic dictionary into Firehose format."""
        data = {'foo': 'bar', 'num': 123}

        result = dictionary_to_firehose_record(data)

        self.assertIsInstance(result, dict)
        self.assertIn('Data', result)
        self.assertIsInstance(result['Data'], bytes)
        decoded = result['Data'].decode('utf-8')
        self.assertTrue(decoded.endswith('\n'))
        json_obj = json.loads(decoded.strip())
        self.assertEqual(json_obj, data)

    def test_empty_dict(self):
        """Tests converting an empty dictionary into Firehose format."""
        data = {}

        result = dictionary_to_firehose_record(data)

        self.assertIsInstance(result, dict)
        self.assertIn('Data', result)
        self.assertIsInstance(result['Data'], bytes)
        decoded = result['Data'].decode('utf-8')
        self.assertTrue(decoded.endswith('\n'))
        self.assertEqual(decoded, '{}\n')

    def test_nested_dict(self):
        """Tests converting a nested dictionary into Firehose format."""
        data = {'outer': {'inner': [1, 2, 3]}, 'flag': True}

        result = dictionary_to_firehose_record(data)

        self.assertIsInstance(result, dict)
        self.assertIn('Data', result)
        self.assertIsInstance(result['Data'], bytes)
        decoded = result['Data'].decode('utf-8')
        json_obj = json.loads(decoded.strip())
        self.assertEqual(json_obj, data)

    def test_special_characters(self):
        """Tests converting a dictionary with special characters into Firehose format."""
        data = {'text': 'newline\nquote"backslash\\'}

        result = dictionary_to_firehose_record(data)

        self.assertIsInstance(result, dict)
        self.assertIn('Data', result)
        self.assertIsInstance(result['Data'], bytes)
        decoded = result['Data'].decode('utf-8')
        json_obj = json.loads(decoded.strip())
        self.assertEqual(json_obj, data)


class TestWriteTrainLocationData(unittest.TestCase):
    """Class for testing write_train_location_data method."""

    def setUp(self):
        """Patch environment variables and common dependencies before each test."""
        self.data_to_write = [{'foo': 'bar'}]

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_success(self, mock_boto_client):
        """Tests a successful write to S3 of train location data."""
        mock_firehose = MagicMock()
        mock_firehose.put_record_batch.return_value = {
            'FailedPutCount': 0,
            'Encrypted': True
        }
        mock_boto_client.return_value = mock_firehose

        write_train_location_data(data_to_write=self.data_to_write, max_retries=5)

        mock_firehose.put_record_batch.assert_called_once_with(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=[dictionary_to_firehose_record(data) for data in self.data_to_write]
        )

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_failed_initial_batch_write(self, mock_boto_client):
        """Tests an initial failed batch write and subsequent successful batch write."""
        mock_firehose = MagicMock()
        mock_firehose.put_record_batch.side_effect = [
            {
                'FailedPutCount': 1,
                'Encrypted': True,
                'RequestResponses': [
                    {
                        'RecordId': '0',
                        'ErrorCode': 'FailedBatchWrite',
                        'ErrorMessage': 'Batch writing records failed'
                    }
                ]
            },
            {
                'FailedPutCount': 0,
                'Encrypted': True
            }
        ]
        mock_boto_client.return_value = mock_firehose

        write_train_location_data(data_to_write=self.data_to_write, max_retries=5)

        mock_firehose.put_record_batch.assert_called_with(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=[dictionary_to_firehose_record(data) for data in self.data_to_write]
        )
        self.assertEqual(mock_firehose.put_record_batch.call_count, 2)

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_failed_all_batch_writes(self, mock_boto_client):
        """Tests when retry attempts are exhausted for batch write."""
        mock_firehose = MagicMock()
        mock_firehose.put_record_batch.return_value = {
            'FailedPutCount': 1,
            'Encrypted': True,
            'RequestResponses': [
                {
                    'RecordId': '0',
                    'ErrorCode': 'FailedBatchWrite',
                    'ErrorMessage': 'Batch writing records failed'
                }
            ]
        }
        mock_boto_client.return_value = mock_firehose

        with self.assertRaises(Exception):
            write_train_location_data(data_to_write=self.data_to_write, max_retries=5)

        mock_firehose.put_record_batch.assert_called_with(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=[dictionary_to_firehose_record(data) for data in self.data_to_write]
        )
        self.assertEqual(mock_firehose.put_record_batch.call_count, 5)

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_boto3_error(self, mock_boto_client):
        """Tests a non-retryable boto3 exception with writing data to Firehose."""
        mock_firehose = MagicMock()
        mock_firehose.put_record_batch.side_effect = botocore.exceptions.ClientError(
            error_response={'Error': {'Code': 'ResourceNotFoundException'}},
            operation_name='PutRecordBatch'
        )
        mock_boto_client.return_value = mock_firehose
        with self.assertRaises(botocore.exceptions.ClientError):
            write_train_location_data(data_to_write=self.data_to_write, max_retries=5)

        mock_firehose.put_record_batch.assert_called_once_with(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=[dictionary_to_firehose_record(data) for data in self.data_to_write]
        )

    @patch('lambdas.get_train_status.get_train_status.boto3.client')
    def test_write_train_location_data_boto3_retryable_error(self, mock_boto_client):
        """Tests a retryable boto3 exception with calling put_record_batch retries 3 times."""
        mock_firehose = MagicMock()
        mock_firehose.put_record_batch.side_effect = botocore.exceptions.ClientError(
            error_response={'Error': {'Code': 'InternalServerError'}},
            operation_name='PutRecordBatch'
        )
        mock_boto_client.return_value = mock_firehose
        with self.assertRaises(botocore.exceptions.ClientError):
            write_train_location_data(data_to_write=self.data_to_write, max_retries=5)

        mock_firehose.put_record_batch.assert_called_with(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=[dictionary_to_firehose_record(data) for data in self.data_to_write]
        )
        self.assertEqual(mock_firehose.put_record_batch.call_count, 3)


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
    @patch('lambdas.get_train_status.get_train_status.datetime')
    def test_lambda_handler_success(self, mock_datetime, mock_train_locations_write, mock_train_locations):
        """Tests successful (happy path) lambda_handler invocation."""
        mock_current_timestamp = datetime.datetime(
            year=2025,
            month=6,
            day=25,
            hour=10,
            minute=30,
            second=25,
            microsecond=45,
            tzinfo=zoneinfo.ZoneInfo('America/Chicago')
        )
        mock_current_date = mock_current_timestamp.date()
        mock_datetime.datetime.now.return_value = mock_current_timestamp
        mock_datetime.datetime.side_effect = lambda *args, **kwargs: datetime.datetime(*args, **kwargs)
        mock_datetime.datetime.now.date.return_value = mock_current_date
        mock_train_locations_write.return_value = None
        mock_train_locations.return_value = MOCK_TRAIN_LOCATION_RESPONSE
        expected_output_data = [
            {
                'train_id': f'{mock_current_date}#Purple#110#5',
                'current_timestamp': mock_current_timestamp.isoformat(),
                'prediction_generated_timestamp': '2025-06-20T12:42:56',
                'destination_station': 'Forest Park',
                'next_station': 'Belmont',
                'next_station_arrival_time': '2025-06-20T12:43:56',
                'is_approaching_station': '1',
                'is_train_delayed': '0'
            }
        ]

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
        mock_train_locations_write.assert_called_once_with(
            data_to_write=expected_output_data,
            max_retries=5
        )

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
