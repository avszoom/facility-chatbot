"""DynamoDB adapter boundary for the AWS stage.

Implement `OperationsRepository` with a single-table layout, conditional writes
for versions/idempotency, and DynamoDB TTL for job leases. No service code changes.
"""


class DynamoDBOperationsRepository:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("DynamoDB adapter is an AWS-stage module and is not configured locally")
