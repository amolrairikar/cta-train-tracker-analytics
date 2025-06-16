"""Module containing code for Lambda function to fetch CTA train statuses from the Train Tracker API."""
from typing import Dict, Any
import logging
import json

# Set up logger
# TODO: convert the logging level into an environment variable
logger = logging.getLogger('cta-train-analytics-get-train-status')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda fetching recently played tracks."""
    # Log basic information about the Lambda function
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    # Parse event body from SQS
    trigger_event_body = json.loads(event.get('Records', [])[0].get('body', '{}'))
    logger.info('Train line abbrev: %s', trigger_event_body.get('train_line_abbrev', 'N/A'))
    logger.info('Train line: %s', trigger_event_body.get('train_line', 'N/A'))

    return {
        'statusCode': 200,
        'body': 'Execution successful'
    }
