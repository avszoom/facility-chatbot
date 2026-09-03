from __future__ import annotations

import signal
import subprocess
import sys
import time


def main() -> None:
    commands = [
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        [sys.executable, "-m", "backend.app.scheduling.local_worker"],
        ["npm", "--prefix", "frontend", "run", "dev"],
    ]
    processes = [subprocess.Popen(command) for command in commands]

    def stop(*_args) -> None:
        for process in processes:
            process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        raise SystemExit(next((process.returncode for process in processes if process.returncode), 0))
    finally:
        stop()


if __name__ == "__main__":
    main()
