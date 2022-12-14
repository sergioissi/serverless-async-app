import base64
import json
import os
import time
import random
import sys
sys.path.insert(0, 'src/task1/vendor')
import requests
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    SQSEvent,
)
from aws_lambda_powertools import Metrics, Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths


logger = Logger(service = "DemoXRayV2_Logger")
tracer = Tracer(service = "DemoXRayV2_Tracer")
metrics = Metrics(namespace="DemoXRayV2", service= "DemoXRayV2_Metrix")
API_URL = os.environ["TASKS_API_URL"]


'''using logger.inject_lambda_context decorator to inject key 
information from Lambda context into every log.
also setting log_event=True to automatically log each incoming request for debugging'''
@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path = correlation_paths.API_GATEWAY_REST, log_event = True)
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context):
    for record in event.records:
        task_id = record.message_attributes["TaskId"].string_value
        task_type = record.message_attributes["TaskType"].string_value
        payload = _decode_payload(record.body)

        print(f"Starting task {task_type} with id {task_id}")
        _update_task_status(task_id, "IN_PROGRESS", "Task started")
        try:
            _do_task(payload)
        except Exception as e:
            print(f"Task with id {task_id} failed: {str(e)}")
            _update_task_status(task_id, "FAILED", str(e))
            continue

        print(f"Task with id {task_id} completed successfully.")
        _update_task_status(task_id, "COMPLETED", "Task completed")


def _do_task(payload: dict):
    # Do something here.
    print(f"Payload: {payload}")
    time.sleep(10)
    if random.randint(1, 4) == 1:
        # Simulate failure in some invocations
        raise Exception("Task failed somehow")


def _decode_payload(payload: str) -> dict:
    json_string = base64.b64decode(payload.encode("utf-8")).decode("utf-8")
    return json.loads(json_string)


def _update_task_status(task_id: str, status: str, status_msg: str):
    data = {
        "status": status,
        "status_msg": status_msg,
    }

    url = f"{API_URL}/tasks/{task_id}"
    res = requests.patch(url, json=data)

    if res.status_code != 204:
        print(f"Request to API failed: {res.json()}")
        raise Exception("Update task status failed")
