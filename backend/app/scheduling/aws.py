"""AWS scheduling seam.

The AWS slice will translate an EventBridge/SQS message into a WorkflowJob and call
WorkflowService._dispatch through a public message handler. Business rules remain
inside WorkflowService; leasing, retries, and dead-letter handling move to AWS.
"""


class AwsSchedulerNotConfigured(RuntimeError):
    pass
