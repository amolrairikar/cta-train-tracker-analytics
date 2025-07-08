from typing import Dict, Any
import logging
import os
import json

import boto3
import botocore
import botocore.exceptions
from dotenv import load_dotenv
import pandas as pd
from retry_api_exceptions import backoff_on_client_error

# Load environment variables
load_dotenv()

# Set up logger
# TODO: convert the logging level into an environment variable
logger = logging.getLogger('cta-train-analytics-bucket-raw-data')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda writing bucketed raw data to S3."""
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    return {
        'statusCode': 200,
        'body': 'Processed all data successfully'
    }