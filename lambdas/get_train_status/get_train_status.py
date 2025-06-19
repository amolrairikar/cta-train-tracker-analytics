"""Module containing code for Lambda function to fetch CTA train statuses from the Train Tracker API."""
from typing import Dict, Any
import logging
import os
import requests
import datetime
import time

import boto3

from retry_api_exceptions import backoff_on_client_error

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
    base_url = 'lapi.transitchicago.com/api/1.0/ttpositions.aspx'
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

# @backoff_on_client_error
# def write_train_location_data(train_location_data: Dict[str, Any]):
#     """Writes train location data to DynamoDB table."""
#     dynamo_db = boto3.client('dynamodb')
#     dynamo_db.batch_write_item(
#         RequestItems={
#             'cta-train-tracker-location-application-data': []
#         }
#     )

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda fetching recently played tracks."""
    # Log basic information about the Lambda function
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    today_date = datetime.date.today().strftime('%Y-%m-%d')
    ttl_expiry_time = int(time.time()) + (60*60*36)  # Records expire in 36 hours

    train_line_abbrev = event.get('Records', [])[0].get('body', '').get('train_line_abbrev', '')
    train_line = event.get('Records', [])[0].get('body', '').get('train_line', '')
    if not train_line or not train_line_abbrev:
        raise ValueError('Parameters train_line_abbrev and/or train_line were not present in the SQS message payload.')

    locations = get_train_locations(train_line_abbrev=train_line_abbrev)
    trains = locations.get('ctatt', {}).get('route', [])
    if trains:
        request_timestamp = locations['ctatt']['tmst']
        batch_write_items = []
        for train in trains:
            batch_write_items.append(
                {
                    'PutRequest': {
                        'Item': {
                            'TrainId': {'S': f'{today_date}#{train_line}#{train['rn']}#{train['trDr']}'},
                            'UpdatedTimestamp': {'S': request_timestamp},
                            'DestinationStation': {'S': train['destNm']},
                            'NextStation': {'S': train['nextStaNm']},
                            'NextStationArrivalPredictionTime': {'S': train['prdt']},
                            'NextStationArrivalTime': {'S': train['arrT']},
                            'ApproachingStation': {'S': train['isApp']},
                            'TrainDelayed': {'S': train['isDly']},
                            'TimeToExist': {'N': str(ttl_expiry_time)}
                        }
                    }
                }
            )
        logger.info('Train locations: %s', batch_write_items)

    return {
        'statusCode': 200,
        'body': 'Execution successful'
    }
