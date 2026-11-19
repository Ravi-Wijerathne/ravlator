"""
[FR-29, FR-31, FR-32] Process Telemetry, Task Inspector & Diagnostic Logger.
Monitors active Wine processes inside prefixes and manages real-time log streaming.
Decoupled from GUI frameworks.
"""

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ravlator.core.config import Config
from ravlator.core.bottle import BottleManager


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    cpu_percent: float
    mem_percent: float
    name: str
    command: str


class ProcessTelemetry:
    """Queries and manages running processes belonging to a Wine bottle."""

    @classmethod
    def get_log_path(cls, bottle_id: str) -> Path:
        """Path to bottle's persistent output log."""
        b_dir = BottleManager.get_bottle_dir(bottle_id)
        log_dir = b_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "bottle.log"

    @classmethod
    def list_bottle_processes(cls, bottle_id: str) -> List[ProcessInfo]:
        """
        [FR-29] Scans running macOS processes and filters those associated with the bottle.
        """
        b_dir = str(BottleManager.get_bottle_dir(bottle_id))
        processes: List[ProcessInfo] = []

        try:
            # Query Darwin process table
            res = subprocess.run(
                ["ps", "-eo", "pid,ppid,%cpu,%mem,command"],
                capture_output=True,
                text=True,
                check=False
            )
            lines = res.stdout.strip().splitlines()
            if len(lines) <= 1:
                return processes

            for line in lines[1:]:
                parts = line.strip().split(None, 4)
                if len(parts) < 5:
                    continue

                pid_str, ppid_str, cpu_str, mem_str, cmd = parts
                # Match processes referencing this specific bottle's prefix directory or wineserver
                if b_dir in cmd or (f"wine" in cmd.lower() and bottle_id in cmd):
                    try:
                        pid = int(pid_str)
                        ppid = int(ppid_str)
                        cpu = float(cpu_str)
                        mem = float(mem_str)
                        # Extract friendly executable name
                        exe_name = Path(cmd.split()[0]).name
                        processes.append(ProcessInfo(
                            pid=pid,
                            ppid=ppid,
                            cpu_percent=cpu,
                            mem_percent=mem,
                            name=exe_name,
                            command=cmd
                        ))
                    except (ValueError, IndexError):
                        continue

        except Exception:
            pass

        return processes

    @classmethod
    def terminate_process(cls, pid: int, force: bool = False) -> bool:
        """[FR-31] Terminates an individual process by PID."""
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
        except ProcessLookupError:
            return True
        except Exception:
            return False

    @classmethod
    def read_recent_logs(cls, bottle_id: str, max_lines: int = 150) -> str:
        """[FR-32] Reads the tail of the bottle's log file."""
        log_file = cls.get_log_path(bottle_id)
        if not log_file.exists():
            return "No log output recorded yet."

        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception as e:
            return f"Failed to read logs: {e}"

    @classmethod
    def append_log(cls, bottle_id: str, text: str) -> None:
        """Appends output to the bottle's log file."""
        log_file = cls.get_log_path(bottle_id)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
