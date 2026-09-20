#!/usr/bin/env python3
"""Local-only desk state. One JSON command per stdin line; snapshots on stdout.

No shell evaluation, network service, or system settings changes. Timer deadlines
survive a shell restart; completion is persisted before a notification is sent.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "tempered-os"


class Desk:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"note": "", "focus": {}, "completed": {}}
        self.error = ""
        try:
            saved = json.loads(path.read_text())
            if isinstance(saved, dict):
                self.data["note"] = str(saved.get("note", ""))[:16000]
                focus = saved.get("focus", {})
                if isinstance(focus, dict) and focus.get("state") in {"running", "paused", "done"}:
                    total = float(focus.get("total", 1500))
                    deadline = float(focus.get("deadline", 0))
                    remaining = float(focus.get("remaining", 0))
                    if all(math.isfinite(v) for v in (total, deadline, remaining)):
                        self.data["focus"] = {**focus, "total": max(60, min(10800, total)),
                                              "deadline": deadline, "remaining": max(0, remaining)}
                if isinstance(saved.get("completed"), dict):
                    self.data["completed"] = {k: v for k, v in saved["completed"].items()
                                              if isinstance(k, str) and isinstance(v, int) and v >= 0}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            # Preserve the unreadable original for recovery instead of destroying notes.
            self.error = "Could not read saved desk data. Original file preserved."
            if path.exists():
                self.path = path.with_name("desk-recovered.json" if path.name != "desk-recovered.json" else f"desk-recovered-{time.time_ns()}.json")
                if self.path.exists():
                    recovered = Desk(self.path)
                    self.data, self.path = recovered.data, recovered.path

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix=".desk-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def remaining(self, now: float) -> int:
        focus = self.data["focus"]
        if focus.get("state") == "running":
            return max(0, math.ceil(focus["deadline"] - now))
        return max(0, math.ceil(focus.get("remaining", 0)))

    def command(self, message: dict, now: float):
        action = message.get("action")
        focus = self.data["focus"]
        if action == "note":
            value = message.get("text")
            if not isinstance(value, str) or len(value) > 16000:
                raise ValueError("Notes are limited to 16,000 characters.")
            self.data["note"] = value
        elif action == "start":
            minutes = message.get("minutes", 25)
            if not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not 1 <= minutes <= 180:
                raise ValueError("Choose between 1 and 180 minutes.")
            total = round(minutes * 60)
            self.data["focus"] = {"state": "running", "total": total, "deadline": now + total,
                                  "remaining": total, "kind": "break" if message.get("kind") == "break" else "focus"}
        elif action == "pause" and focus.get("state") == "running":
            focus.update(remaining=self.remaining(now), state="paused")
        elif action == "resume" and focus.get("state") == "paused":
            focus.update(deadline=now + focus["remaining"], state="running")
        elif action == "reset":
            self.data["focus"] = {}
        else:
            raise ValueError("Unknown desk action.")
        self.error = ""
        self.save()

    def tick(self, now: float) -> str | None:
        focus = self.data["focus"]
        if focus.get("state") != "running" or self.remaining(now) > 0:
            return None
        focus.update(state="done", remaining=0)
        today = dt.date.fromtimestamp(now).isoformat()
        if focus.get("kind") != "break":
            self.data["completed"][today] = self.data["completed"].get(today, 0) + 1
        self.data["completed"] = dict(sorted(self.data["completed"].items())[-31:])
        self.save()
        return "Break complete" if focus.get("kind") == "break" else "Focus complete"

    def snapshot(self, now: float) -> dict:
        today = dt.date.fromtimestamp(now).isoformat()
        return {**self.data, "remaining": self.remaining(now),
                "today": self.data["completed"].get(today, 0), "error": self.error}


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    desk = Desk(STATE_DIR / "desk.json")
    last = None
    pending = b""
    while True:
        now = time.time()
        try:
            completion = desk.tick(now)
            if completion:
                subprocess.Popen(["notify-send", "-a", "Tempered Desk", "-i", "appointment-soon-symbolic",
                                  completion, "Take a breath. Your desk will be here."],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            desk.error = "Couldn't save desk state. Check your available disk space."
        snapshot = json.dumps(desk.snapshot(now), ensure_ascii=False)
        if snapshot != last:
            print(snapshot, flush=True)
            last = snapshot
        readable, _, _ = select.select([sys.stdin], [], [], 0.5)
        if readable:
            chunk = os.read(sys.stdin.fileno(), 65536)
            if not chunk:
                return
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                try:
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError("Invalid desk command.")
                    desk.command(message, time.time())
                except (ValueError, TypeError, OSError) as error:
                    desk.error = str(error)
            if len(pending) > 100000:
                pending = b""
                desk.error = "Desk command was too large."


if __name__ == "__main__":
    main()
