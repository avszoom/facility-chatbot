from __future__ import annotations

import inspect

from backend.app.agents.runtime import OpenAIStrandsRuntime, StrandsAgentRuntime
from backend.app.config import Settings


def main() -> None:
    import strands

    assert hasattr(strands, "Agent")
    assert "structured_output_model=CoordinatorDirective" in inspect.getsource(
        StrandsAgentRuntime.coordinate
    )
    assert "structured_output_model=SpecialistReport" in inspect.getsource(
        StrandsAgentRuntime._run_specialist
    )
    assert "for iteration in range" in inspect.getsource(StrandsAgentRuntime.decide)
    runtime = StrandsAgentRuntime(Settings())
    assert runtime.name == "strands-bedrock"
    openai_runtime = OpenAIStrandsRuntime(
        Settings(**{"openai_api_key": "verification-placeholder"})
    )
    assert openai_runtime.name == "strands-openai"
    print("PASS Strands SDK imported; coordinator directives and specialist reports share the typed OpenAI/Bedrock boundary.")
    print("NOTE Live invocation uses AGENT_RUNTIME=openai plus OPENAI_API_KEY, or AGENT_RUNTIME=bedrock plus AWS credentials.")


if __name__ == "__main__":
    main()
