#!/usr/bin/env python3
"""Private launcher pins and recent app IDs. No commands or search terms stored."""
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile


def update(data, action, app_id):
    pins = [x for x in data.get("pins", []) if isinstance(x, str)][:100] if isinstance(data.get("pins"), list) else []
    recent = [x for x in data.get("recent", []) if isinstance(x, str)][:30] if isinstance(data.get("recent"), list) else []
    if action == "pin":
        pins = [x for x in pins if x != app_id] if app_id in pins else [*pins, app_id][-100:]
    elif action == "record":
        recent = [app_id, *[x for x in recent if x != app_id]][:30]
    return {"pins": pins, "recent": recent}


def main():
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "tempered-os"
    path = base / "launcher.json"
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (base / "launcher.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        action = sys.argv[1] if len(sys.argv) > 1 else "get"
        app_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if action not in {"get", "pin", "record"} or (action != "get" and (not app_id or len(app_id) > 512)):
            return 2
        data = update(data, action, app_id)
        if action != "get":
            fd, name = tempfile.mkstemp(prefix=".launcher-", dir=base)
            try:
                with os.fdopen(fd, "w") as handle:
                    json.dump(data, handle)
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        print(json.dumps(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
