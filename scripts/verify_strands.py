from __future__ import annotations

import inspect

from backend.app.agents.runtime import OpenAIStrandsRuntime, StrandsAgentRuntime
from backend.app.config import Settings


def main() -> None:
    import strands

    assert hasattr(strands, "Agent")
    assert "structured_output_model" in inspect.getsource(StrandsAgentRuntime.decide)
    runtime = StrandsAgentRuntime(Settings())
    assert runtime.name == "strands-bedrock"
    openai_runtime = OpenAIStrandsRuntime(
        Settings(**{"openai_api_key": "verification-placeholder"})
    )
    assert openai_runtime.name == "strands-openai"
    print("PASS Strands SDK imported; OpenAI and Bedrock model adapters share the typed runtime boundary.")
    print("NOTE Live invocation uses AGENT_RUNTIME=openai plus OPENAI_API_KEY, or AGENT_RUNTIME=bedrock plus AWS credentials.")


if __name__ == "__main__":
    main()
