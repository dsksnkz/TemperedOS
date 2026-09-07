#!/usr/bin/env python3
"""Small newline-json feed for the Tempered island."""

from __future__ import annotations

import json
import os
import re
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


def volume() -> tuple[int, bool]:
    raw = command(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], "Volume: 0")
    match = re.search(r"([0-9.]+)", raw)
    return round(float(match.group(1)) * 100) if match else 0, "MUTED" in raw


def workspace() -> tuple[int, str]:
    raw = command(["hyprctl", "activeworkspace", "-j"], "{}")
    try:
        data = json.loads(raw)
        return int(data.get("id", 1)), str(data.get("name", "1"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 1, "1"


def media() -> tuple[str, str, bool]:
    template = "{{status}}\t{{artist}}\t{{title}}"
    raw = command(["playerctl", "metadata", "--format", template])
    if not raw:
        return "", "", False
    state, artist, title = (raw.split("\t", 2) + ["", ""])[:3]
    return artist, title, state == "Playing"


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


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def main() -> None:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    previous = None
    while True:
        cpu, previous = cpu_sample(previous)
        level, muted = volume()
        ws_id, ws_name = workspace()
        artist, title, playing = media()
        payload = {
            "cpu": cpu,
            "memory": memory_percent(),
            "volume": level,
            "muted": muted,
            "workspace": ws_id,
            "workspaceName": ws_name,
            "network": network(),
            "battery": battery(),
            "artist": artist,
            "title": title,
            "playing": playing,
            "palette": read_json(PALETTE),
            "settings": read_json(SETTINGS),
        }
        print(json.dumps(payload, separators=(",", ":")), flush=True)
        time.sleep(1.5)


if __name__ == "__main__":
    main()
