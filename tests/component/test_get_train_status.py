mock_event = {
    "Records": [
        {
            "messageId": "id123",
            "receiptHandle": "this_is_a_random_string",
            "body": {"train_line_abbrev": "P", "train_line": "Purple"},
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

class MockLambdaContext:
    """Mock class for AWS Lambda context."""

    def __init__(self):
        """Initializes mock Lambda context with constant attributes for tests."""
        self.aws_request_id = 'test-request-id'
        self.function_name = 'test-function-name'
        self.function_version = 'test-function-version'

# lambda_handler(event=mock_event, context=MockLambdaContext())