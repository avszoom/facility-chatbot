from __future__ import annotations

from typing import Protocol


class WorkerPort(Protocol):
    """Run durable workflow jobs; SQS/Lambda can provide the same delivery semantics."""

    def run_once(self) -> int: ...
    def run_forever(self) -> None: ...
