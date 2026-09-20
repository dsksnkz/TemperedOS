"""Local-only Shelf data and shortcuts. No GTK or desktop mutations on import."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "tempered-os"


def read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".shelf-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def user_directory(name: str) -> Path:
    """Read XDG folders without evaluating a shell or arbitrary variables."""
    fallback = HOME / {"DOWNLOAD": "Downloads", "DOCUMENTS": "Documents", "PICTURES": "Pictures"}.get(name.upper(), name.title())
    try:
        source = (CONFIG / "user-dirs.dirs").read_text()
    except OSError:
        return fallback
    match = re.search(r'^XDG_' + re.escape(name.upper()) + r'_DIR="([^"\n]+)"$', source, re.M)
    if not match:
        return fallback
    value = match[1].replace("${HOME}", str(HOME)).replace("$HOME", str(HOME))
    return Path(value) if value.startswith("/") and "$" not in value else fallback


def screenshot_directory() -> Path:
    return user_directory("PICTURES") / "Screenshots"


class ShelfStore:
    def __init__(self, path: Path | None = None):
        self.path = path or STATE / "shelf.json"
        self.error = ""
        data = read_json(self.path)
        if self.path.exists() and not isinstance(data, dict):
            self.error = "Saved Shelf data could not be read. The original is preserved."
            self.path = self.path.with_name("shelf-recovered.json")
            data = read_json(self.path, {})
        data = data if isinstance(data, dict) else {}
        self.places = [item for item in data.get("places", []) if isinstance(item, dict)
                       and isinstance(item.get("path"), str) and item["path"].startswith("/")
                       and isinstance(item.get("id"), str)] if isinstance(data.get("places"), list) else []
        self.colors = [value for value in data.get("colors", []) if isinstance(value, str)
                       and re.fullmatch(r"#[0-9a-fA-F]{6}", value)] if isinstance(data.get("colors"), list) else []

    def save(self):
        write_json(self.path, {"places": self.places[:100], "colors": self.colors[:16]})

    def pin(self, path: Path) -> bool:
        path = path.expanduser().resolve(strict=True)
        if not (path.is_file() or path.is_dir()):
            raise ValueError("Choose a regular file or folder")
        if any(item["path"] == str(path) for item in self.places):
            return False
        if len(self.places) >= 100:
            raise ValueError("Shelf holds up to 100 pinned items. Unpin one to add another.")
        self.places.insert(0, {"id": uuid.uuid4().hex, "path": str(path), "name": path.name or str(path)})
        self.save()
        return True

    def unpin(self, identity: str):
        self.places = [item for item in self.places if item["id"] != identity]
        self.save()

    def color(self, value: str):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("The picker did not return a hex color")
        value = value.upper()
        self.colors = [value] + [item for item in self.colors if item != value]
        self.save()


def captures(folder: Path | None = None, limit=120) -> list[Path]:
    folder = folder or screenshot_directory()
    if not folder.is_dir():
        return []
    candidates = []
    for item in folder.iterdir():
        try:
            if not item.name.startswith(".") and not item.is_symlink() and item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                candidates.append((item.stat().st_mtime_ns, item))
        except OSError:
            continue
    return [item for _, item in sorted(candidates, key=lambda entry: entry[0], reverse=True)[:limit]]


def capture_name(folder: Path) -> Path:
    return folder / f"Tempered-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.png"


COMMAND_NAMES = {
    "terminal": "Open terminal", "files": "Open files", "launcher": "Open launcher",
    "tempered-capture": "Capture an area", "tempered-control": "Open Control Center",
    "tempered-settings": "Open Settings", "tempered-wallpaper-picker": "Change wallpaper",
    "zeditor": "Open Zed", "app.zen_browser.zen": "Open Zen",
    "clipse": "Clipboard history", "swaync-client": "Notifications", "hyprlock": "Lock screen",
    "tempered-power": "Power menu", "tempered-brightness change 5": "Increase brightness",
    "tempered-brightness change -5": "Decrease brightness", "AudioRaise": "Increase volume",
}


def shortcuts(source: Path | None = None) -> list[dict]:
    """Describe literal binds in Tempered's Lua config; never execute its source."""
    source = source or CONFIG / "hypr/hyprland.lua"
    try:
        text = source.read_text()
    except OSError:
        return []
    mod = re.search(r'local\s+mod\s*=\s*"([^"\n]+)"', text)
    modifier = mod[1].title() if mod else "Super"
    result = []
    for line in text.splitlines():
        match = re.match(r'\s*hl\.bind\((mod\s*\.\.\s*)?"([^"\n]+)",\s*(.+)', line)
        if not match:
            continue
        key = (modifier + match[2] if match[1] else match[2]).strip()
        rhs = match[3]
        label = next((title for command, title in COMMAND_NAMES.items() if command in rhs), "")
        if not label:
            named = {
                "window.close": "Close window", "window.fullscreen": "Toggle fullscreen",
                "window.float": "Toggle floating", "window.pseudo": "Toggle pseudotiling",
                "togglesplit": "Change split direction", "window.drag": "Move window",
                "window.resize": "Resize window", "workspace.toggle_special": "Show scratch workspace",
                "set-mute @DEFAULT_AUDIO_SINK@": "Mute sound", "set-mute @DEFAULT_AUDIO_SOURCE@": "Mute microphone",
                "playerctl next": "Next track", "playerctl previous": "Previous track", "playerctl play-pause": "Play / pause",
            }
            label = next((title for command, title in named.items() if command in rhs), "")
        if not label and "set-volume" in rhs:
            label = "Increase volume" if "5%+" in rhs else "Decrease volume"
        if not label and "direction =" in rhs:
            direction = re.search(r'direction\s*=\s*"([a-z]+)"', rhs)
            label = "Focus " + direction[1] if direction else "Move focus"
        if not label and "workspace" in rhs:
            target = re.search(r'workspace\s*=\s*(?:"([^"]+)"|(\d+))', rhs)
            destination = (target[1] or target[2]) if target else "another workspace"
            label = ("Move window to " if "window.move" in rhs else "Switch to ") + destination
        if not label:
            label = "Custom action"
        result.append({"keys": key.replace("ESCAPE", "Esc").replace("RETURN", "Enter").replace("SPACE", "Space")
                       .replace("SHIFT", "Shift").replace("mouse_up", "Scroll up").replace("mouse_down", "Scroll down"),
                       "name": label, "detail": rhs.split(", { repeating")[0][:220]})
    # These two bindings are generated by the stock loop, not literal lines.
    if re.search(r'for workspace = 1, 9 do', text) and 'mod .. " + " .. workspace' in text:
        result.extend([{"keys": modifier + " + 1…9", "name": "Switch workspace", "detail": "Numbered workspaces"},
                       {"keys": modifier + " + Shift + 1…9", "name": "Move window to workspace", "detail": "Numbered workspaces"}])
    return result
