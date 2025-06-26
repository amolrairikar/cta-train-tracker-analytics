"""Module containing code for Lambda function to fetch CTA train statuses from the Train Tracker API."""
from typing import Dict, Any, List
import logging
import os
import datetime
import zoneinfo
import json

import boto3
from dotenv import load_dotenv
import requests

from retry_api_exceptions import backoff_on_client_error

# Load environment variables
load_dotenv()

# Set up logger
# TODO: convert the logging level into an environment variable
logger = logging.getLogger('cta-train-analytics-get-train-status')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


@backoff_on_client_error
def get_train_locations(train_line_abbrev: str) -> Dict[str, Any]:
    """Makes request to Train Locations API endpoint to get locations of all trains for a given line."""
    base_url = 'https://lapi.transitchicago.com/api/1.0/ttpositions.aspx'
    query_params = {
        'rt': train_line_abbrev,
        'key': os.environ['API_KEY'],
        'outputType': 'JSON'
    }
    logger.info('Making request to %s with parameters %s', base_url, query_params)
    response = requests.get(url=base_url, params=query_params)
    response.raise_for_status()
    logger.info('Successfully retrieved locations for train line: %s', train_line_abbrev)
    locations = response.json()
    return locations


def dictionary_to_firehose_record(data):
    """Converts a python dictionary into a format that Firehose accepts."""
    json_line = json.dumps(data) + "\n"
    return {'Data': json_line.encode('utf-8')}


@backoff_on_client_error
def write_train_location_data(data_to_write: List[Dict[str, Any]], max_retries: int):
    """Writes train location data to Firehose. If errors occur, retries until retry_attempts
        are exhausted."""
    firehose = boto3.client('firehose')
    remaining = [dictionary_to_firehose_record(data) for data in data_to_write]
    attempts = 0
    while remaining and attempts < max_retries:
        response = firehose.put_record_batch(
            DeliveryStreamName='cta-train-analytics-stream',
            Records=remaining
        )
        failed_count = response['FailedPutCount']
        if failed_count > 0:
            logger.info(f'{failed_count} records failed on attempt {attempts}, retrying batch send with failed records')
            failed_records = [
                remaining[i] for i, r in enumerate(response['RequestResponses']) if 'ErrorCode' in r
            ]
            remaining = failed_records
            attempts += 1
        else:
            return

    if remaining:
        raise Exception(f'Failed to send {len(remaining)} records after {max_retries} retries.')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda getting train locations."""
    # Log basic information about the Lambda function
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    timezone = zoneinfo.ZoneInfo('America/Chicago')
    today = datetime.datetime.now(timezone)
    today_date = today.date().strftime('%Y-%m-%d')
    today_datetime = today.isoformat()

    sqs_message_body = event.get('Records', [])[0].get('body', '')
    train_line_abbrev = json.loads(sqs_message_body).get('train_line_abbrev', '')
    train_line = json.loads(sqs_message_body).get('train_line', '')
    if not train_line_abbrev or not train_line:
        raise ValueError('Parameters train_line_abbrev and/or train_line were not present in the SQS message payload.')

    locations = get_train_locations(train_line_abbrev=train_line_abbrev)
    trains = locations.get('ctatt', {}).get('route', [])
    if trains:
        trains_in_service = trains[0].get('train', [])
        if trains_in_service:
            train_location_data = []
            for train in trains_in_service:
                train_location_data.append(
                    {
                        'train_id': f'{today_date}#{train_line}#{train['rn']}#{train['trDr']}',
                        'current_timestamp': today_datetime,
                        'prediction_generated_timestamp': train['prdt'],
                        'destination_station': train['destNm'],
                        'next_station': train['nextStaNm'],
                        'next_station_arrival_time': train['arrT'],
                        'is_approaching_station': train['isApp'],
                        'is_train_delayed': train['isDly']
                    }
                )
            write_train_location_data(data_to_write=train_location_data, max_retries=5)
        else:
            logger.info('No trains running currently')
            return {
                'statusCode': 204,
                'body': 'No records written due to no trains running'
            }
    else:
        message = 'Route or ctatt object not present in API response'
        logger.info(message)
        raise KeyError(message)

    return {
        'statusCode': 200,
        'body': 'Execution successful'
    }
