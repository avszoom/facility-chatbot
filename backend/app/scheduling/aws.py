"""AWS scheduling and pub/sub seam.

The AWS adapter will publish the same message envelope through EventBridge or SNS and
consume it from SQS/Lambda. EventBridge Scheduler supplies future wake-ups; SQS owns
visibility leases, retry, and dead-letter redrive. Business rules and idempotency stay
inside the existing workflow handlers.
"""


class AwsSchedulerNotConfigured(RuntimeError):
    pass
