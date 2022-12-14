import os
import json
import base64
import sys
from uuid import uuid4
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import And, Attr
sys.path.insert(0, 'src/api/vendor')
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths


logger = Logger(service = "DemoXRayV2_Logger")
tracer = Tracer(service = "DemoXRayV2_Tracer")
metrics = Metrics(namespace="DemoXRayV2", service= "DemoXRayV2_Metrix")

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


class Error(Exception):
    pass


class InvalidTaskStateError(Error):
    pass


class TaskNotFoundError(Error):
    pass

@tracer.capture_method
def create_task(task_type: str, payload: dict, ttl: int) -> str:
    task_id = str(uuid4())
    table.put_item(
        Item={
            "id": task_id,
            "task_type": task_type,
            "status": "CREATED",
            "payload": _encode(payload),
            "created_time": _get_timestamp(),
            "TimeToLive": ttl
        }
    )

    return {"id": task_id}


@tracer.capture_method
def get_task(task_id: str) -> dict:
    res = table.get_item(
        Key={
            "id": task_id,
        },
    )

    item = res.get("Item")
    if not item:
        raise TaskNotFoundError

    return item


@tracer.capture_method
def update_task(task_id: str, status: str, status_msg: str):
    cond = Attr("id").exists()

    if status == "IN_PROGRESS":
        cond = And(cond, Attr("status").eq("CREATED"))

    try:
        table.update_item(
            Key={
                "id": task_id,
            },
            UpdateExpression="set #S=:s, status_msg=:m, updated_time=:t",
            # status is reserved
            ExpressionAttributeNames={
                "#S": "status",
            },
            ExpressionAttributeValues={
                ":s": status,
                ":m": status_msg,
                ":t": _get_timestamp(),
            },
            ConditionExpression=cond,
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise InvalidTaskStateError


@tracer.capture_method
def list_tasks(next_token: str = None) -> dict:
    scan_args = {
        "Limit": 10,
    }

    if next_token:
        scan_args["ExclusiveStartKey"] = _decode(next_token)

    res = table.scan(**scan_args)
    response = {"tasks": res["Items"]}

    if "LastEvaluatedKey" in res:
        response["next_token"] = _encode(res["LastEvaluatedKey"])

    return response


def _encode(data: dict) -> str:
    json_string = json.dumps(data)
    return base64.b64encode(json_string.encode("utf-8")).decode("utf-8")


def _decode(data: str) -> dict:
    json_string = base64.b64decode(data.encode("utf-8")).decode("utf-8")
    return json.loads(json_string)


def _get_timestamp() -> int:
    return int(datetime.utcnow().timestamp())
