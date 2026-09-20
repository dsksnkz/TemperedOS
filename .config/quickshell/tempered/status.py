#!/usr/bin/env python3
"""Small newline-json feed for the Tempered island."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
PALETTE = CONFIG / "tempered" / "palette.json"
SETTINGS = CONFIG / "tempered" / "settings.json"


def command(args: list[str], fallback: str = "") -> str:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=1.2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    return result.stdout.strip() if result.returncode == 0 else fallback


def cpu_sample(previous: tuple[int, int] | None) -> tuple[int, tuple[int, int]]:
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    ticks = [int(value) for value in fields]
    idle = ticks[3] + ticks[4]
    total = sum(ticks)
    if previous is None:
        return 0, (idle, total)
    idle_delta = idle - previous[0]
    total_delta = max(1, total - previous[1])
    return round(100 * (1 - idle_delta / total_delta)), (idle, total)


def memory_percent() -> int:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.split()[0])
    return round(100 * (1 - values.get("MemAvailable", 0) / max(1, values.get("MemTotal", 1))))


def network() -> str:
    raw = command(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"])
    for line in raw.splitlines():
        kind, state, name = (line.split(":", 2) + ["", ""])[:3]
        if state == "connected" and kind in {"ethernet", "wifi"}:
            return name or kind.title()
    return "Offline"


def battery() -> int:
    supplies = sorted(Path("/sys/class/power_supply").glob("BAT*/capacity"))
    try:
        return int(supplies[0].read_text().strip()) if supplies else -1
    except (OSError, ValueError):
        return -1


def brightness() -> int:
    cached = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tempered-os/brightness-value"
    try:
        return max(0, min(100, int(cached.read_text().strip())))
    except (OSError, ValueError):
        return 50


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def brightness_error() -> str:
    path = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tempered-os/brightness-error"
    try:
        return path.read_text().strip()[:180]
    except OSError:
        return ""


def main() -> None:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    previous = None
    slow = {
        "network": "Offline", "battery": -1, "cpu": 0, "memory": 0,
        "palette": read_json(PALETTE), "settings": read_json(SETTINGS),
    }
    next_stats = next_network = next_files = 0.0
    last = None
    while True:
        now = time.monotonic()
        # Audio, media and workspaces use native event-driven Quickshell services.
        # Only /proc and small local files are sampled here; one feed for all screens.
        if now >= next_stats:
            cpu, previous = cpu_sample(previous)
            slow.update(cpu=cpu, memory=memory_percent())
            next_stats = now + 2.0
        if now >= next_network:
            slow.update(network=network(), battery=battery())
            next_network = now + 12.0
        if now >= next_files:
            slow.update(palette=read_json(PALETTE), settings=read_json(SETTINGS))
            next_files = now + 1.0
        payload = {
            **slow,
            "brightness": brightness(),
            "brightnessError": brightness_error(),
            "user": os.environ.get("USER", "You"),
        }
        encoded = json.dumps(payload, separators=(",", ":"))
        if encoded != last:
            print(encoded, flush=True)
            last = encoded
        time.sleep(0.5)


if __name__ == "__main__":
    main()
