"""AgentCore runtime adapter boundary for the AWS stage.

The deployed entry point will deserialize a Ticket/context payload, invoke the
same Strands `AgentDecision` contract, and return only the typed decision. Durable
ticket orchestration remains outside the model runtime.
"""


class AgentCoreRuntime:
    name = "strands-agentcore"

    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("AgentCore runtime is an AWS-stage module and is not configured locally")
