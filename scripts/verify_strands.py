from __future__ import annotations

import inspect

from backend.app.agents.runtime import StrandsAgentRuntime
from backend.app.config import Settings


def main() -> None:
    import strands

    assert hasattr(strands, "Agent")
    assert "structured_output_model" in inspect.getsource(StrandsAgentRuntime.decide)
    runtime = StrandsAgentRuntime(Settings())
    assert runtime.name == "strands-local"
    print("PASS Strands SDK imported; typed runtime boundary and structured output are configured.")
    print("NOTE A live Bedrock invocation requires AGENT_RUNTIME=strands and valid AWS credentials.")


if __name__ == "__main__":
    main()
