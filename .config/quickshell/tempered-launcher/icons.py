#!/usr/bin/env python3
"""Resolve desktop icons across installed themes, including legacy app icons."""
import json
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

themes = []
for name in ("Papirus-Dark", "breeze-dark", "Adwaita", "AdwaitaLegacy", "hicolor"):
    theme = Gtk.IconTheme.new()
    theme.set_theme_name(name)
    themes.append(theme)

resolved = {}
for app in Gio.AppInfo.get_all():
    icon = app.get_icon()
    if isinstance(icon, Gio.FileIcon):
        file = icon.get_file()
        path = file.get_path()
        fallback = Path(__file__).with_name("application.svg").as_uri()
        uri = fallback
        if path:
            try:
                with open(path, "rb") as source:
                    content_type, _ = Gio.content_type_guess(path, source.read(4096))
                if content_type.startswith("image/"):
                    uri = Path(path).as_uri()
            except (OSError, ValueError):
                pass
            resolved[path] = uri
            resolved[file.get_uri()] = uri
            resolved[icon.to_string()] = uri
        continue
    if not isinstance(icon, Gio.ThemedIcon):
        continue
    for name in icon.get_names():
        if name in resolved:
            continue
        for theme in themes:
            if not theme.has_icon(name):
                continue
            paintable = theme.lookup_icon(name, None, 32, 1, Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_REGULAR)
            file = paintable.get_file()
            path = file.get_path() if file else None
            if path and Path(path).is_file():
                resolved[name] = Path(path).as_uri()
                break

print(json.dumps(resolved))
