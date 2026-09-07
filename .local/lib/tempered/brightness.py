#!/usr/bin/env python3
"""Control the active monitor backlight, preferring external DDC/CI displays."""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tempered-os"
BUS_FILE = CACHE_DIR / "ddc-bus"
LOCK_FILE = CACHE_DIR / "brightness.lock"
MINIMUM = 5


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
            return run(["ddcutil", "--bus", bus, "setvcp", "10", str(value)]).returncode == 0
        if shutil.which("brightnessctl"):
            return run(["brightnessctl", "set", f"{value}%"]).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bus, current = find_ddc()
        if current is None:
            current = laptop_value()
        if current is None:
            print("Brightness control unavailable", file=sys.stderr)
            return 1

        action = sys.argv[1] if len(sys.argv) > 1 else "get"
        if action == "get":
            print(current)
            return 0
        try:
            if action == "set" and len(sys.argv) == 3:
                target = int(sys.argv[2])
            elif action == "change" and len(sys.argv) == 3:
                target = current + int(sys.argv[2])
            else:
                raise ValueError
        except ValueError:
            print("Usage: tempered-brightness [get|set PERCENT|change DELTA]", file=sys.stderr)
            return 2

        target = max(MINIMUM, min(100, target))
        if not set_value(bus, target):
            print("Could not set monitor brightness", file=sys.stderr)
            return 1
        print(target)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
