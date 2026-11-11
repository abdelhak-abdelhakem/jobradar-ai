"""
Runs the pipeline once. A systemd timer can call it on a schedule (see src/scheduling.py).

  python -m scheduler.run_daily
"""
import fcntl
import os

from src import config
from src.agents.graph import compile_graph
from src.agents.state import initial_state


def main() -> bool:
    """
    Runs the pipeline unless another run holds the lock, and returns whether it ran.
    Two runs at once would score every job and send every message twice. The operating system releases
    the lock when the process ends, even after a crash, so a stale lock can't block later runs.
    """
    os.makedirs(os.path.dirname(config.RUN_LOCK_PATH), exist_ok=True)
    with open(config.RUN_LOCK_PATH, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("A run is already in progress, so this one was skipped.")
            return False
        compile_graph().invoke(initial_state())
        return True


if __name__ == "__main__":
    main()
