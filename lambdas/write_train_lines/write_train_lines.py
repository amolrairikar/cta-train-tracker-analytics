from typing import Dict, Any
import logging
import os

import boto3
import botocore
import botocore.exceptions
from dotenv import load_dotenv
from retry_api_exceptions import backoff_on_client_error

# Load environment variables
load_dotenv()

# Set up logger
# TODO: convert the logging level into an environment variable
logger = logging.getLogger('cta-train-analytics-write-train-lines')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

cta_train_lines = {
    'Red': 'Red',
    'Blue': 'Blue',
    'Brn': 'Brown',
    'G': 'Green',
    'Org': 'Orange',
    'P': 'Purple',
    'Pink': 'Pink'
}

@backoff_on_client_error
def get_sqs_queue_url(sqs_client, queue_name: str) -> str:
    """Get the URL of the specified SQS queue."""
    logger.info('Retrieving SQS queue URL for: %s', queue_name)
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = response['QueueUrl']
        logger.info('Retrieved SQS queue URL: %s', queue_url)
        return queue_url
    except botocore.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'QueueDoesNotExist':
            logger.error('Queue does not exist: %s', queue_name)
            raise
        logger.error('Error retrieving SQS queue URL: %s', e)
        raise

@backoff_on_client_error
def send_message_to_sqs(sqs_client, queue_url: str, message_body: Dict[str, Any]) -> None:
    """Send a message to the specified SQS queue."""
    logger.info('Sending message to SQS queue: %s', queue_url)
    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=str(message_body)
        )
        logger.info('Successfully sent message to SQS queue')
    except botocore.exceptions.ClientError as e:
        logger.error('Failed to send message to SQS queue: %s', e)
        raise


@backoff_on_client_error
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda writing CTA train lines to SQS."""
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    try:
        queue_name = os.environ['SQS_QUEUE_NAME']
        logger.info('SQS queue name: %s', queue_name)
    except KeyError as e:
        logger.error('Environment variable SQS_QUEUE_NAME not set: %s', e)
        raise

    sqs = boto3.client('sqs', region_name=os.environ['REGION_NAME'])
    queue_url = get_sqs_queue_url(
        sqs_client=sqs,
        queue_name=queue_name
    )

    for train_abbrev, train_line in cta_train_lines.items():
        logger.info('Processing train line: %s', train_line)
        message_body = {
            'train_line_abbrev': train_abbrev,
            'train_line': train_line
        }
        send_message_to_sqs(
            sqs_client=sqs,
            queue_url=queue_url,
            message_body=message_body
        )
    return {
        'statusCode': 200,
        'body': 'Processed all train lines'
    }
