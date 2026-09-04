from __future__ import annotations

import signal
import subprocess
import sys
import time

from backend.app.config import Settings


def operations_commands(worker_count: int) -> list[list[str]]:
    return [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        *[
            [sys.executable, "-m", "backend.app.scheduling.local_worker"]
            for _ in range(worker_count)
        ],
    ]


def main() -> None:
    settings = Settings.from_env()
    processes = [
        subprocess.Popen(command)
        for command in operations_commands(settings.agent_worker_count)
    ]

    def stop(*_args) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        raise SystemExit(
            next((process.returncode for process in processes if process.returncode), 0)
        )
    finally:
        stop()


if __name__ == "__main__":
    main()
