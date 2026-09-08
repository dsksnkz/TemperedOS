#!/usr/bin/env python3
"""Wallpaper palette compiler for Tempered OS."""

from __future__ import annotations

import colorsys
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps


HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
TEMPERED = CONFIG / "tempered"
SETTINGS_FILE = TEMPERED / "settings.json"
PALETTE_FILE = TEMPERED / "palette.json"
DEFAULT_WALLPAPER = TEMPERED / "wallpapers" / "default.png"


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(path.suffix + ".new")
    scratch.write_text(text, encoding="utf-8")
    scratch.replace(path)


def rgb_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(left * (1 - amount) + right * amount) for left, right in zip(a, b))


def luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        value /= 255
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def chroma(rgb: tuple[int, int, int]) -> float:
    high, low = max(rgb), min(rgb)
    return (high - low) / 255


def rotate_hue(rgb: tuple[int, int, int], degrees: float) -> tuple[int, int, int]:
    red, green, blue = (part / 255 for part in rgb)
    hue, saturation, lightness = colorsys.rgb_to_hls(red, green, blue)
    hue = (hue + degrees / 360) % 1
    return tuple(round(part * 255) for part in colorsys.hls_to_rgb(hue, saturation, lightness))


def energize(rgb: tuple[int, int, int], dark_surface: bool) -> tuple[int, int, int]:
    """Keep wallpaper hue while making interactive color reliably vivid and legible."""
    red, green, blue = (part / 255 for part in rgb)
    hue, saturation, lightness = colorsys.rgb_to_hls(red, green, blue)
    saturation = max(0.48, min(0.88, saturation * 1.12))
    lightness = max(0.54 if dark_surface else 0.38, min(0.68 if dark_surface else 0.56, lightness))
    return tuple(round(part * 255) for part in colorsys.hls_to_rgb(hue, saturation, lightness))


def hue_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    def hue(rgb: tuple[int, int, int]) -> float:
        red, green, blue = (part / 255 for part in rgb)
        return colorsys.rgb_to_hls(red, green, blue)[0]

    distance = abs(hue(a) - hue(b))
    return min(distance, 1 - distance)


def palette_from(path: Path) -> dict[str, str]:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((160, 160))
        reduced = image.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        colors = reduced.getcolors() or []
        swatches = [(count, tuple(reduced.palette.palette[index * 3:index * 3 + 3])) for count, index in colors]

    swatches.sort(reverse=True)
    dominant = swatches[0][1] if swatches else (58, 72, 88)
    accent_pool = [entry for entry in swatches if 0.16 < luminance(entry[1]) < 0.78]
    accent_source = max(accent_pool or swatches, key=lambda item: item[0] * (0.42 + chroma(item[1]) * 2.8))[1]

    # Wallpaper hue is material, not the canvas. Tempered always uses a dark,
    # high-contrast foundation and reserves brighter extracted colors for state.
    accent = energize(accent_source, True)
    base = mix(dominant, (6, 9, 14), 0.90)
    if luminance(base) > 0.025:
        base = mix(base, (4, 7, 11), 0.30)
    text = (242, 247, 252)
    muted = mix(text, base, 0.48)
    surface = mix(base, accent, 0.10)
    raised = mix(base, text, 0.09)
    border = mix(accent, text, 0.40)
    secondary_pool = [entry for entry in accent_pool if entry[1] != accent_source]
    if secondary_pool:
        accent_2 = max(
            secondary_pool,
            key=lambda item: item[0] * (0.3 + chroma(item[1]) * 2.2) * (0.5 + hue_distance(accent, item[1]) * 2.5),
        )[1]
    else:
        accent_2 = rotate_hue(accent, 34)
    accent_2 = energize(accent_2, True)

    return {
        "background": rgb_hex(base),
        "surface": rgb_hex(surface),
        "surfaceRaised": rgb_hex(raised),
        "text": rgb_hex(text),
        "muted": rgb_hex(muted),
        "accent": rgb_hex(accent),
        "accent2": rgb_hex(accent_2),
        "border": rgb_hex(border),
        "danger": "#ff6b78",
        "dark": True,
    }


def emit_files(colors: dict[str, str], wallpaper: Path) -> None:
    payload = {**colors, "wallpaper": str(wallpaper)}
    atomic_text(PALETTE_FILE, json.dumps(payload, indent=2) + "\n")

    kitty = f'''foreground {colors["text"]}
background {colors["background"]}
selection_foreground {colors["background"]}
selection_background {colors["accent"]}
cursor {colors["accent"]}
color0 {colors["background"]}
color1 {colors["danger"]}
color2 {colors["accent2"]}
color3 {colors["border"]}
color4 {colors["accent"]}
color5 {colors["accent2"]}
color6 {colors["border"]}
color7 {colors["text"]}
'''
    atomic_text(CONFIG / "kitty" / "tempered-colors.conf", kitty)

    gtk = f'''@define-color tempered_bg_color {colors["background"]};
@define-color tempered_surface_color {colors["surface"]};
@define-color tempered_accent_color {colors["accent"]};
@define-color tempered_fg_color {colors["text"]};
@define-color tempered_muted_color {colors["muted"]};
@define-color tempered_border_color {colors["border"]};
'''
    for folder in ("gtk-3.0", "gtk-4.0", "swaync", "wlogout"):
        atomic_text(CONFIG / folder / "tempered-colors.css", gtk)

    paper = f'''splash = false

wallpaper {{
    monitor =
    path = {wallpaper}
    fit_mode = cover
}}
'''
    atomic_text(CONFIG / "hypr" / "hyprpaper.conf", paper)

    picker_colors = {
        "base": colors["background"], "mantle": colors["surface"],
        "crust": colors["background"], "text": colors["text"],
        "subtext0": colors["muted"], "subtext1": colors["border"],
        "surface0": colors["surface"], "surface1": colors["surfaceRaised"],
        "surface2": colors["border"], "overlay0": colors["muted"],
        "overlay1": colors["border"], "overlay2": colors["text"],
        "blue": colors["accent"], "sapphire": colors["accent2"],
        "peach": colors["accent2"], "green": colors["accent"],
        "red": colors["danger"], "mauve": colors["accent2"],
        "pink": colors["accent2"], "yellow": colors["border"],
        "maroon": colors["danger"], "teal": colors["accent"],
    }
    atomic_text(Path("/tmp/qs_colors.json"), json.dumps(picker_colors) + "\n")


def notify_desktop(colors: dict[str, str], wallpaper: Path) -> None:
    accent = colors["accent"].lstrip("#")
    border = colors["border"].lstrip("#")
    commands = [
        ["hyprctl", "keyword", "general:col.active_border", f"rgba({accent}ee)"],
        ["hyprctl", "keyword", "general:col.inactive_border", f"rgba({border}45)"],
        ["hyprctl", "hyprpaper", "wallpaper", f",{wallpaper},cover"],
    ]
    for command in commands:
        try:
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for schema_key, value in (
        (("org.gnome.desktop.interface", "color-scheme"), "prefer-dark"),
        (("org.gnome.desktop.interface", "gtk-theme"), "adw-gtk3-dark"),
    ):
        try:
            subprocess.run(
                ["gsettings", "set", schema_key[0], schema_key[1], value],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    shell = CONFIG / "quickshell/tempered/shell.qml"
    try:
        subprocess.run(
            ["qs", "ipc", "--path", str(shell), "call", "tempered", "recolor"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def main() -> int:
    settings = read_json(SETTINGS_FILE)
    requested = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(settings.get("wallpaper", DEFAULT_WALLPAPER))
    wallpaper = requested.resolve()
    if not wallpaper.is_file():
        print(f"Tempered OS: wallpaper not found: {wallpaper}", file=sys.stderr)
        return 2
    try:
        colors = palette_from(wallpaper)
    except (OSError, ValueError) as error:
        print(f"Tempered OS: cannot read wallpaper: {error}", file=sys.stderr)
        return 3

    settings["wallpaper"] = str(wallpaper)
    atomic_text(SETTINGS_FILE, json.dumps(settings, indent=2) + "\n")
    emit_files(colors, wallpaper)
    notify_desktop(colors, wallpaper)
    print(json.dumps({**colors, "wallpaper": str(wallpaper)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
