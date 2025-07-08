from typing import Dict, Any
import logging
import os
import json

import awswrangler as wr
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


@backoff_on_client_error
def read_partitioned_json_data(s3_partition_path: str) -> pd.DataFrame:
    """Read partitioned JSON data from S3 into a DataFrame."""
    logger.info('Reading JSON data from S3 path: %s', s3_partition_path)
    df = wr.s3.read_json(
        path=s3_partition_path,
        dataset=True,
        path_suffix='.json',
        dtype_backend='pyarrow'
    )
    logger.info('Successfully read JSON data from S3 path: %s', s3_partition_path)
    return df


@backoff_on_client_error
def write_partitioned_parquet_data(df: pd.DataFrame, s3_path: str, partition_column: str) -> None:
    """Write DataFrame to S3 as partitioned Parquet data."""
    logger.info('Writing DataFrame as partitioned Parquet data to S3 path: %s', s3_path)
    wr.s3.to_parquet(
        df=df,
        path=s3_path,
        dataset=True,
        mode='append',
        partition_cols=[partition_column],
        dtype_backend='pyarrow'
    )
    logger.info('Data successfully written to S3: %s', s3_path)


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