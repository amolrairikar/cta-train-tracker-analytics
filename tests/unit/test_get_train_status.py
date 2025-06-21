# """Module for unit testing of the get_train_status lambda handler function."""
# import unittest
# from unittest.mock import patch, MagicMock
# import os
# import json

# import botocore
# import botocore.exceptions
# import requests

# from lambdas.get_train_status.get_train_status import get_train_locations, write_train_location_data, lambda_handler
# from tests.helper_files.mock_batch_write_objects import MOCK_BATCH_WRITE_PAYLOAD, MOCK_BATCH_WRITE_PROCESSED_RESPONSE, MOCK_BATCH_WRITE_UNPROCESSED_RESPONSE


# class TestGetTrainLocations(unittest.TestCase):
#     """Class for testing get_train_locations method."""

#     def setUp(self):
#         """Patch environment variables and common dependencies before each test."""
#         self.env_patcher = patch.dict(
#             os.environ,
#             {
#                 'API_KEY': 'api-key'
#             }
#         )
#         self.env_patcher.start()

#     def tearDown(self):
#         """Stop all patches after each test."""
#         self.env_patcher.stop()

#     @patch('lambdas.get_train_status.get_train_status.requests.get')
#     def test_get_train_locations_success(self, mock_get):
#         """Tests a successful API request to the Train Locations CTA API endpoint."""
#         with open('tests/helper_files/mock_train_location_response.json') as mock_json:
#             mock_response = MagicMock()
#             mock_response.raise_for_status = MagicMock()
#             mock_response.json.return_value = mock_json
#             mock_get.return_value = mock_response

#             get_train_locations(train_line_abbrev='P')

#             mock_get.assert_called_once_with(
#                 url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
#                 params = {
#                     'rt': 'P',
#                     'key': 'api-key',
#                     'outputType': 'JSON'
#                 }
#             )

#     @patch('lambdas.get_train_status.get_train_status.requests.get')
#     def test_get_train_locations_failure(self, mock_get):
#         """Tests when an error occurs with the API request to the Train Locations CTA API endpoint."""
#         response_mock = MagicMock()
#         response_mock.status_code = 400
#         http_error = requests.exceptions.HTTPError(
#             '400 Client Error: Bad Request for url'
#         )
#         http_error.response = response_mock
#         mock_response = MagicMock()
#         mock_response.raise_for_status.side_effect = http_error
#         mock_get.return_value = mock_response

#         with self.assertRaises(requests.exceptions.HTTPError):
#             get_train_locations(train_line_abbrev='P')

#         mock_get.assert_called_once_with(
#             url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
#             params = {
#                 'rt': 'P',
#                 'key': 'api-key',
#                 'outputType': 'JSON'
#             }
#         )

#     @patch('lambdas.get_train_status.get_train_status.requests.get')
#     def test_get_train_locations_retry(self, mock_get):
#         """Tests the API request to the Train Locations CTA API endpoint gets retried for the appropriate HTTP codes."""
#         response_mock = MagicMock()
#         response_mock.status_code = 429
#         http_error = requests.exceptions.HTTPError(
#             '429 Client Error: Too many requests'
#         )
#         http_error.response = response_mock
#         mock_response = MagicMock()
#         mock_response.raise_for_status.side_effect = http_error
#         mock_get.return_value = mock_response

#         with self.assertRaises(requests.exceptions.HTTPError):
#             get_train_locations(train_line_abbrev='P')

#         mock_get.assert_called_with(
#             url='https://lapi.transitchicago.com/api/1.0/ttpositions.aspx',
#             params = {
#                 'rt': 'P',
#                 'key': 'api-key',
#                 'outputType': 'JSON'
#             }
#         )
#         self.assertEqual(mock_get.call_count, 3)
