"""Daemon helpers — PID file management, process lifecycle, log access."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Default paths under ~/.jagabot/
_BASE_DIR = Path.home() / ".jagabot"
PID_FILE = _BASE_DIR / "service.pid"
LOG_FILE = _BASE_DIR / "service.log"


def _ensure_base_dir() -> None:
    _BASE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# PID helpers
# ---------------------------------------------------------------------------

def read_pid() -> int | None:
    """Return the PID stored on disk, or *None* if absent / corrupt."""
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def write_pid(pid: int) -> None:
    _ensure_base_dir()
    PID_FILE.write_text(str(pid))


def remove_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


def is_running(pid: int | None = None) -> bool:
    """Check whether a process is alive (signal 0 probe)."""
    pid = pid if pid is not None else read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------

def start_service(port: int = 18790, verbose: bool = False) -> int:
    """Spawn ``jagabot gateway`` as a detached background process.

    Returns the child PID on success, raises on failure.
    """
    existing = read_pid()
    if existing and is_running(existing):
        raise RuntimeError(f"Service already running (PID {existing})")

    # Clean stale PID if process is gone
    if existing:
        remove_pid()

    _ensure_base_dir()

    cmd = [sys.executable, "-m", "jagabot", "gateway", "--port", str(port)]
    if verbose:
        cmd.append("--verbose")

    log_fh = open(LOG_FILE, "a")  # noqa: SIM115 – kept open for child

    # Build environment — inherit current env and ensure API keys are set
    import json
    _env = os.environ.copy()
    try:
        _config = json.loads((Path.home() / ".jagabot" / "config.json").read_text())
        _providers = _config.get("providers", {})
        for _name, _pdata in _providers.items():
            _key = _pdata.get("apiKey", "")
            if _key:
                _env_map = {
                    "deepseek": "DEEPSEEK_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "gemini": "GEMINI_API_KEY",
                    "dashscope": "DASHSCOPE_API_KEY",
                }
                if _name in _env_map:
                    _env.setdefault(_env_map[_name], _key)
    except Exception:
        pass  # Fall back to inherited env

    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # detach from controlling terminal
        env=_env,
    )

    # Give the process a moment to fail fast (bad config, port conflict, …)
    time.sleep(0.5)
    if proc.poll() is not None:
        log_fh.close()
        tail = tail_log(20)
        raise RuntimeError(
            f"Service exited immediately (code {proc.returncode}).\n"
            f"Last log lines:\n{tail}"
        )

    write_pid(proc.pid)
    return proc.pid


def stop_service(timeout: int = 10) -> bool:
    """Send SIGTERM and wait up to *timeout* seconds.  Returns True if stopped."""
    pid = read_pid()
    if pid is None or not is_running(pid):
        remove_pid()
        return True  # nothing to stop

    os.kill(pid, signal.SIGTERM)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_running(pid):
            remove_pid()
            return True
        time.sleep(0.3)

    # Force kill
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    time.sleep(0.2)
    remove_pid()
    return not is_running(pid)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def service_status() -> dict:
    """Return a status dict: running, pid, uptime (approx), log_file."""
    pid = read_pid()
    running = is_running(pid)

    info: dict = {
        "running": running,
        "pid": pid if running else None,
        "pid_file": str(PID_FILE),
        "log_file": str(LOG_FILE),
    }

    if running and pid:
        # Rough uptime from /proc on Linux
        try:
            stat_path = Path(f"/proc/{pid}/stat")
            if stat_path.exists():
                boot = float(Path("/proc/stat").read_text().split("btime ")[1].split()[0])
                ticks = os.sysconf("SC_CLK_TCK")
                start_ticks = int(stat_path.read_text().split(")")[1].split()[19])
                start_epoch = boot + start_ticks / ticks
                info["uptime_s"] = int(time.time() - start_epoch)
        except Exception:
            pass

    if not running and pid:
        remove_pid()
        info["pid"] = None

    return info


# ---------------------------------------------------------------------------
# Log access
# ---------------------------------------------------------------------------

def tail_log(lines: int = 50) -> str:
    """Return the last *lines* lines from the service log file."""
    if not LOG_FILE.exists():
        return "(no log file)"
    try:
        text = LOG_FILE.read_text(errors="replace")
        all_lines = text.splitlines()
        return "\n".join(all_lines[-lines:])
    except Exception as exc:
        return f"(error reading log: {exc})"


def follow_log() -> None:
    """Stream the log file to stdout (like ``tail -f``).  Blocks until Ctrl-C."""
    if not LOG_FILE.exists():
        _ensure_base_dir()
        LOG_FILE.touch()

    try:
        proc = subprocess.run(
            ["tail", "-f", str(LOG_FILE)],
            stdin=subprocess.DEVNULL,
        )
    except KeyboardInterrupt:
        pass
