import os
import sys
import boto3
sys.path.insert(0, 'src/publish/vendor')
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    DynamoDBStreamEvent,
)
from aws_lambda_powertools import Metrics, Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths


logger = Logger(service = "DemoXRayV2_Logger")
tracer = Tracer(service = "DemoXRayV2_Tracer")
metrics = Metrics(namespace="DemoXRayV2", service= "DemoXRayV2_Metrix")
topic = boto3.resource("sns").Topic(os.environ["TOPIC_ARN"])


'''using logger.inject_lambda_context decorator to inject key 
information from Lambda context into every log.
also setting log_event=True to automatically log each incoming request for debugging'''
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path = correlation_paths.API_GATEWAY_REST, log_event = True)
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=DynamoDBStreamEvent)
def handler(event: DynamoDBStreamEvent, _):
    for record in event.records:
        task_id = record.dynamodb.keys["id"].get_value
        task_type = record.dynamodb.new_image["task_type"].get_value
        payload = record.dynamodb.new_image["payload"].get_value

        res = topic.publish(
            MessageAttributes={
                "TaskId": {
                    "DataType": "String",
                    "StringValue": task_id,
                },
                "TaskType": {
                    "DataType": "String",
                    "StringValue": task_type,
                },
            },
            Message=payload,
        )

        print(f"Message {res['MessageId']} published.")
