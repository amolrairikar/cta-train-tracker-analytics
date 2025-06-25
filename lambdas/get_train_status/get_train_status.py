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


@backoff_on_client_error
def write_train_location_data(output_data: List[Dict[str, Any]]):
    """Writes train location data to S3."""
    s3 = boto3.client('s3')
    json_data = json.dumps(output_data, indent=4)
    logger.info('Attempting to write output data to S3')
    timezone = zoneinfo.ZoneInfo('America/Chicago')
    s3.put_object(
        Bucket=os.environ['S3_BUCKET_NAME'],
        Key=f'raw/load_date={datetime.date.today(timezone).strftime('%Y-%m-%d')}/{datetime.datetime.now(timezone).strftime('%Y%m%d%H%M%S%f')}.json',
        Body=json_data,
        ContentType='application/json'
    )
    logger.info('Successfully wrote data to S3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda getting train locations."""
    # Log basic information about the Lambda function
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    timezone = zoneinfo.ZoneInfo('America/Chicago')
    today = datetime.datetime.now(timezone).date()
    today_date = today.strftime('%Y-%m-%d')

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
            output_data = []
            for train in trains_in_service:
                output_data.append(
                    {
                        'TrainId': f'{today_date}#{train_line}#{train['rn']}#{train['trDr']}',
                        'PredictionGeneratedTimestamp': train['prdt'],
                        'DestinationStation': train['destNm'],
                        'NextStation': train['nextStaNm'],
                        'NextStationArrivalTime': train['arrT'],
                        'ApproachingStation': train['isApp'],
                        'TrainDelayed': train['isDly']
                    }
                )
            write_train_location_data(output_data=output_data)
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
