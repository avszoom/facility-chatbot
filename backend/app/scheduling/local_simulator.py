from __future__ import annotations

import signal
from threading import Event

from backend.app.system import build_system


class LocalBuildingSimulator:
    """Continuously advances the local building world independently of the agent worker."""

    def __init__(self):
        self.system = build_system()
        self.stopped = Event()

    def run_forever(self) -> None:
        while not self.stopped.wait(0.5):
            self.system.building.advance_sensors()

    def stop(self, *_args) -> None:
        self.stopped.set()


def main() -> None:
    simulator = LocalBuildingSimulator()
    signal.signal(signal.SIGTERM, simulator.stop)
    signal.signal(signal.SIGINT, simulator.stop)
    simulator.run_forever()


if __name__ == "__main__":
    main()
