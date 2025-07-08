from typing import Dict, Any, List
import logging
import os
import json
import datetime
import zoneinfo
import uuid

import boto3
from dotenv import load_dotenv
import pyarrow as pa
import pyarrow.parquet as pq
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
def get_object_keys(s3_client: boto3.client, bucket_name: str, prefix: str) -> List[str]:
    """Retrieves a list of object keys within the specified S3 bucket and prefix."""
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    json_files = []
    for page in page_iterator:
        for obj in page.get('Contents', []):
            logger.info('Found object: %s', obj['Key'])
            json_files.append(obj['Key'])
    return json_files


@backoff_on_client_error
def read_s3_object(s3_client: boto3.client, bucket_name: str, key: str) -> List[Dict[str, Any]]:
    """Reads a JSON object from S3 and returns it as a list of dictionaries."""
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    data = response['Body'].read().decode('utf-8')
    records = []
    for line in data.strip().split('\n'):
        if line.strip():
            records.append(json.loads(line))
    logger.info('Read %d records from S3 object: %s', len(records), key)
    return records


def write_local_parquet_file(data: List[Dict[str, Any]]) -> None:
    """Writes the provided data to a Parquet file at /tmp directory."""
    table = pa.Table.from_pylist(data)
    output_dir = f'/tmp'
    os.makedirs(name=output_dir, exist_ok=True)
    pq.write_table(table=table, where=f'{output_dir}/{uuid.uuid4()}.parquet')


@backoff_on_client_error
def upload_parquet_to_s3(s3_client: boto3.client, local_dir: str, bucket_name: str, prefix: str) -> None:
    """Uploads Parquet files from the local directory to the specified S3 bucket and prefix."""
    for root, _, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(path=local_path, start=local_dir)
            s3_key = os.path.join(prefix, relative_path).replace('\\', '/')
            logger.info(f'Uploading {local_path} to s3://{bucket_name}/{s3_key}')
            s3_client.upload_file(Filename=local_path, Bucket=bucket_name, Key=s3_key)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler function for the Lambda writing bucketed raw data to S3."""
    logger.info('Begin Lambda execution')
    logger.info(f'Lambda request ID: {context.aws_request_id}')
    logger.info(f'Lambda function name: {context.function_name}')
    logger.info(f'Lambda function version: {context.function_version}')
    logger.info(f'Event: {event}')

    timezone = zoneinfo.ZoneInfo('America/Chicago')
    prev_day = datetime.datetime.now(timezone) - datetime.timedelta(days=1)

    s3 = boto3.client('s3')
    s3_bucket_name = os.environ['S3_BUCKET_NAME']

    json_files = get_object_keys(
        s3_client=s3,
        bucket_name=s3_bucket_name,
        prefix=f'raw/{prev_day.year}/{prev_day.month:02d}/{prev_day.day:02d}/'
    )
    json_data = []
    for file in json_files:
        file_records = read_s3_object(
            s3_client=s3,
            bucket_name=s3_bucket_name,
            key=file
        )
        json_data.extend(file_records)
    logger.info('Total records read from S3: %d', len(json_data))
    write_local_parquet_file(
        data=json_data
    )
    upload_parquet_to_s3(
        s3_client=s3,
        local_dir='/tmp',
        bucket_name=s3_bucket_name,
        prefix=f'processed/load_date={prev_day.year}-{prev_day.month:02d}-{prev_day.day:02d}/'
    )

    return {
        'statusCode': 200,
        'body': 'Processed all data successfully'
    }

class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'

lambda_handler(
    event={'key': 'value'},
    context=MockLambdaContext()
)
