#!/usr/bin/env python3
"""Control the active monitor backlight, preferring external DDC/CI displays."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tempered-os"
BUS_FILE = CACHE_DIR / "ddc-bus"
LOCK_FILE = CACHE_DIR / "brightness.lock"
VALUE_FILE = CACHE_DIR / "brightness-value"
REQUEST_FILE = CACHE_DIR / "brightness-request.json"
REQUEST_LOCK = CACHE_DIR / "brightness-request.lock"
ERROR_FILE = CACHE_DIR / "brightness-error"
MINIMUM = 5
DDC_MAXIMUM: dict[str, int] = {}


def run(args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )


def ddc_value(bus: str) -> int | None:
    try:
        result = run(["ddcutil", "--bus", bus, "getvcp", "10", "--brief"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\bC\s+(\d+)\s+(\d+)\b", result.stdout)
    if result.returncode or not match:
        return None
    current, maximum = map(int, match.groups())
    DDC_MAXIMUM[bus] = maximum
    return round(current * 100 / maximum) if maximum else None


def find_ddc() -> tuple[str | None, int | None]:
    if not shutil.which("ddcutil"):
        return None, None

    candidates: list[str] = []
    configured = os.environ.get("TEMPERED_DDC_BUS", "").removeprefix("/dev/i2c-")
    if configured.isdigit():
        candidates.append(configured)
    try:
        cached = BUS_FILE.read_text(encoding="utf-8").strip()
        if cached.isdigit() and cached not in candidates:
            candidates.append(cached)
    except OSError:
        pass

    for bus in candidates:
        value = ddc_value(bus)
        if value is not None:
            return bus, value

    try:
        detected = run(["ddcutil", "detect", "--brief"], timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        detected = ""
    valid_section = detected.split("Invalid display", 1)[0]
    for bus in re.findall(r"I2C bus:\s+/dev/i2c-(\d+)", valid_section):
        value = ddc_value(bus)
        if value is not None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            BUS_FILE.write_text(bus + "\n", encoding="utf-8")
            return bus, value
    return None, None


def laptop_value() -> int | None:
    if not shutil.which("brightnessctl"):
        return None
    try:
        result = run(["brightnessctl", "-m"])
        return int(result.stdout.split(",")[3].rstrip("%"))
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def set_value(bus: str | None, value: int) -> bool:
    value = max(MINIMUM, min(100, value))
    try:
        if bus:
            raw = round(value * DDC_MAXIMUM.get(bus, 100) / 100)
            return run(["ddcutil", "--bus", bus, "setvcp", "10", str(raw), "--noverify"]).returncode == 0
        if shutil.which("brightnessctl"):
            return run(["brightnessctl", "set", f"{value}%"]).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def atomic_write(path: Path, text: str) -> None:
    fd, scratch = tempfile.mkstemp(prefix=".brightness-", dir=CACHE_DIR)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(scratch, path)
    finally:
        if os.path.exists(scratch):
            os.unlink(scratch)


def cached_value() -> int | None:
    try:
        return max(MINIMUM, min(100, int(VALUE_FILE.read_text())))
    except (OSError, ValueError):
        return None


def request() -> dict:
    try:
        data = json.loads(REQUEST_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def submit(action: str, value: int) -> int:
    """A latest-wins mailbox, not a queue of stale monitor writes.

    Producers publish while holding the short request lock. The worker releases
    its hardware lock *inside* that same lock when the mailbox is drained; a
    request arriving during shutdown therefore always elects another worker.
    """
    with REQUEST_LOCK.open("a") as guard, LOCK_FILE.open("a") as worker:
        fcntl.flock(guard, fcntl.LOCK_EX)
        pending = request()
        current = cached_value()
        if action == "change":
            if pending.get("pending") and time.time() - pending.get("created", 0) < 30:
                current = pending["target"]
            if current is None:
                _, current = find_ddc()
                if current is None:
                    current = laptop_value()
            if current is None:
                print("Brightness control unavailable", file=sys.stderr)
                return 1
            value += current
        target = max(MINIMUM, min(100, value))
        pending = {"target": target, "serial": time.time_ns(), "created": time.time(), "pending": True}
        atomic_write(REQUEST_FILE, json.dumps(pending))
        try:
            fcntl.flock(worker, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(target)
            return 0  # Accepted by the current worker; no additional DDC process.
        fcntl.flock(guard, fcntl.LOCK_UN)

        bus, detected = find_ddc()
        available = detected is not None or laptop_value() is not None
        while True:
            pending = request()
            target = pending["target"]
            success = available and set_value(bus, target)
            if success:
                atomic_write(VALUE_FILE, f"{target}\n")
                atomic_write(ERROR_FILE, "")
            else:
                atomic_write(ERROR_FILE, "Monitor brightness is unavailable. Check DDC/CI or backlight permissions.")
            fcntl.flock(guard, fcntl.LOCK_EX)
            newest = request()
            if newest.get("serial") == pending.get("serial"):
                newest["pending"] = False
                atomic_write(REQUEST_FILE, json.dumps(newest))
                fcntl.flock(worker, fcntl.LOCK_UN)
                if success:
                    print(target)
                else:
                    print("Could not set monitor brightness", file=sys.stderr)
                return 0 if success else 1
            fcntl.flock(guard, fcntl.LOCK_UN)


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "get"
    try:
        if action not in {"get", "set", "change"} or (action == "get" and len(sys.argv) > 2):
            raise ValueError
        value = int(sys.argv[2]) if action != "get" and len(sys.argv) == 3 else None
        if action != "get" and value is None:
            raise ValueError
    except ValueError:
        print("Usage: tempered-brightness [get|set PERCENT|change DELTA]", file=sys.stderr)
        return 2
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if action != "get":
        return submit(action, value)
    # Readers hold the mailbox guard until the hardware lock is released, so a
    # writer cannot mistake a one-shot read for a worker that will drain it.
    with REQUEST_LOCK.open("a") as guard, LOCK_FILE.open("a") as lock:
        fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            current = cached_value()
        else:
            _, current = find_ddc()
            if current is None:
                current = laptop_value()
            if current is not None:
                atomic_write(VALUE_FILE, f"{current}\n")
        if current is None:
            print("Brightness control unavailable", file=sys.stderr)
            return 1
        print(current)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
