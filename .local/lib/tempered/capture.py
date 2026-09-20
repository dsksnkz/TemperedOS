#!/usr/bin/env python3
"""Screenshot capture with explicit modes, collision-free files and safe cancellation."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from shelf_core import capture_name, screenshot_directory


class Cancelled(Exception):
    pass


def execute(args, *, input=None, timeout=15):
    result = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip()[:400] or f"{args[0]} failed")
    return result.stdout


def selection(mode: str) -> list[str]:
    if mode == "screen":
        monitors = json.loads(execute(["hyprctl", "monitors", "-j"]))
        monitor = next((item for item in monitors if item.get("focused")), None)
        if not monitor:
            raise RuntimeError("No focused monitor is available")
        return ["-o", monitor["name"]]
    if mode == "all":
        return []
    command = ["slurp"]
    data = None
    if mode == "window":
        monitors = json.loads(execute(["hyprctl", "monitors", "-j"]))
        workspaces = {item.get("activeWorkspace", {}).get("id") for item in monitors}
        workspaces.update(item.get("specialWorkspace", {}).get("id") for item in monitors if item.get("specialWorkspace", {}).get("id"))
        windows = json.loads(execute(["hyprctl", "clients", "-j"]))
        rectangles = []
        for item in windows:
            if item.get("mapped") and not item.get("hidden") and item.get("workspace", {}).get("id") in workspaces:
                x, y = item["at"]
                width, height = item["size"]
                rectangles.append(f"{int(x)},{int(y)} {int(width)}x{int(height)}")
        if not rectangles:
            raise RuntimeError("No visible windows to capture")
        command.append("-r")
        data = ("\n".join(rectangles) + "\n").encode()
    result = subprocess.run(command, input=data, capture_output=True, timeout=120)
    if result.returncode or not result.stdout.strip():
        raise Cancelled()
    return ["-g", result.stdout.decode().strip()]


def capture(mode: str, delay: int, copy: bool, folder: Path | None = None) -> tuple[Path, str]:
    if mode not in {"area", "window", "screen", "all"} or delay not in {0, 3, 5, 10}:
        raise ValueError("Unsupported capture option")
    time.sleep(delay)
    arguments = selection(mode)
    folder = folder or screenshot_directory()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = capture_name(folder)
    fd, temporary = tempfile.mkstemp(prefix=".capture-", suffix=".png", dir=folder)
    os.close(fd)
    try:
        execute(["grim", "-t", "png", *arguments, temporary], timeout=30)
        if Path(temporary).stat().st_size == 0:
            raise RuntimeError("The compositor returned an empty image")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    warning = ""
    if copy:
        try:
            execute(["wl-copy", "--type", "image/png"], input=target.read_bytes(), timeout=5)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            warning = "Saved, but the clipboard could not be updated."
    return target, warning


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="area", choices=("area", "window", "screen", "all"))
    parser.add_argument("--delay", type=int, choices=(0, 3, 5, 10), default=0)
    parser.add_argument("--no-copy", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", Path.home() / ".cache/tempered-os"))
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (runtime / "tempered-capture.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("A capture is already in progress. Finish or cancel it first.", file=sys.stderr)
            return 1
        try:
            target, warning = capture(args.mode, args.delay, not args.no_copy)
            print(target)
            if warning:
                print(warning, file=sys.stderr)
            if not args.quiet:
                try:
                    subprocess.run(["notify-send", "-a", "Tempered OS", "-i", str(target), "Captured",
                                    warning or ("Saved" if args.no_copy else "Saved and copied")], timeout=3, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            return 0
        except Cancelled:
            return 130
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(str(error), file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
