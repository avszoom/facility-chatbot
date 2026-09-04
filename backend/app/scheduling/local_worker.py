from __future__ import annotations

import signal
from threading import Event

from backend.app.system import ApplicationSystem, build_system


class SQLiteLeasedJobWorker:
    """Consumes durable pub/sub deliveries; SQS/Lambda can replace this adapter."""

    def __init__(self, system: ApplicationSystem):
        self.system = system
        self.stopped = Event()

    def run_once(self) -> int:
        # Claim one bounded step at a time so several worker processes distribute
        # independent ticket workflows instead of one process draining the queue.
        return self.system.operations.process_due(limit=1)

    def run_forever(self) -> None:
        while not self.stopped.wait(self.system.settings.worker_poll_seconds):
            self.run_once()

    def stop(self, *_args) -> None:
        self.stopped.set()


def main() -> None:
    worker = SQLiteLeasedJobWorker(build_system())
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
