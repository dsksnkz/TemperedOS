#!/usr/bin/env python3
"""Tempered OS control room."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402


HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "tempered-os"
SETTINGS_FILE = CONFIG / "tempered" / "settings.json"
THEME_BIN = HOME / ".local/bin/tempered-theme"
SETTINGS_CSS = Path(__file__).with_name("settings.css")

DEFAULTS: dict[str, object] = {
    "display_name": "",
    "profile_image": "",
    "music_visualizer": True,
    "island_feedback": True,
    "wallpaper": str(CONFIG / "tempered/wallpapers/default.png"),
    "adaptive_color": True,
    "glass_opacity": 68,
    "island_width": 50,
    "island_height": 50,
    "island_compact": False,
    "show_seconds": False,
    "rounding": 18,
    "rounding_power": 3.0,
    "gaps_in": 6,
    "gaps_out": 10,
    "blur": True,
    "blur_size": 8,
    "blur_passes": 3,
    "animations": True,
    "animation_speed": 100,
    "reduce_motion": False,
    "inactive_opacity": 96,
    "shadow": True,
    "sensitivity": -0.15,
    "natural_scroll": False,
    "left_handed": False,
    "tap_to_click": True,
    "scroll_factor": 100,
    "repeat_rate": 30,
    "repeat_delay": 450,
    "cursor_size": 20,
    "text_scale": 100,
    "vrr": False,
    "focus_follows_mouse": 1,
    "power_profile": "balanced",
    "idle_lock": 600,
    "dnd": False,
    "display_brightness": 30,
    "output_volume": 25,
    "mic_muted": False,
    "wifi": True,
    "bluetooth": True,
}

ANIMATIONS = [
    ("windows", 4.8, "tempered_release", "popin 78%"),
    ("windowsIn", 5.2, "tempered_release", "popin 74%"),
    ("windowsOut", 4.2, "tempered_quick", "popin 82%"),
    ("windowsMove", 5.0, "tempered_spring", ""),
    ("fade", 4.0, "tempered_soft", ""),
    ("layersIn", 5.2, "tempered_release", "slide top"),
    ("layersOut", 4.5, "tempered_quick", "slide top"),
    ("workspaces", 6.0, "tempered_release", "slidefade 14%"),
    ("workspacesIn", 6.0, "tempered_release", "slidefade 14%"),
    ("workspacesOut", 5.0, "tempered_release", "slidefade 14%"),
    ("specialWorkspace", 5.4, "tempered_spring", "slidefadevert 18%"),
]


def run(args: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def output(args: list[str], fallback: str = "") -> str:
    result = run(args)
    return result.stdout.strip() if result and result.returncode == 0 else fallback


def detached(args: list[str]) -> None:
    try:
        subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        # Missing optional tools should give useful feedback, not a dead button.
        try:
            subprocess.Popen(["notify-send", "-a", "Tempered OS", "Application unavailable",
                              f"{Path(args[0]).name} is not installed or could not start."],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def shell_path() -> str:
    return str(CONFIG / "quickshell/tempered/shell.qml")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(settings: dict[str, object], keys: tuple[str, ...] | None = None) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # A wallpaper update may have changed other preferences since this window opened.
    data = {**read_json(SETTINGS_FILE), **{key: settings[key] for key in keys}} if keys else settings
    fd, name = tempfile.mkstemp(prefix=".settings-", dir=SETTINGS_FILE.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(name, SETTINGS_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load() -> dict[str, object]:
    return {**DEFAULTS, **read_json(SETTINGS_FILE)}


def keyword(name: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    run(["hyprctl", "keyword", name, str(value)])


def apply_animations(settings: dict[str, object]) -> None:
    enabled = bool(settings["animations"]) and not bool(settings["reduce_motion"])
    # Hyprland's speed field is a duration, so a higher UI pace needs a smaller value.
    factor = max(0.5, min(2.0, 100 / float(settings["animation_speed"])))
    for leaf, base, curve, style in ANIMATIONS:
        fields = [f'leaf = "{leaf}"', f"enabled = {'true' if enabled else 'false'}", f"speed = {base * factor:.2f}"]
        fields.append(("spring" if curve == "tempered_spring" else "bezier") + f' = "{curve}"')
        if style:
            fields.append(f'style = "{style}"')
        run(["hyprctl", "eval", "hl.animation({ " + ", ".join(fields) + " })"])


def apply_idle_timeout(value: float | int) -> None:
    """Persist the first lock timeout and restart the managed idle daemon."""
    path = CONFIG / "hypr/hypridle.conf"
    try:
        source = path.read_text(encoding="utf-8")
        updated, replacements = re.subn(
            r"(listener\s*\{\s*timeout\s*=\s*)\d+",
            lambda match: f"{match.group(1)}{round(float(value))}",
            source,
            count=1,
        )
        if replacements != 1:
            return
        scratch = path.with_suffix(".conf.new")
        scratch.write_text(updated, encoding="utf-8")
        scratch.replace(path)
    except OSError:
        return

    run(["systemctl", "--user", "stop", "tempered-hypridle.service"])
    detached([
        "systemd-run", "--user", "--unit=tempered-hypridle", "--collect",
        "hypridle", "-c", str(path),
    ])


def apply_all(settings: dict[str, object]) -> None:
    values = {
        "decoration:rounding": settings["rounding"],
        "decoration:rounding_power": settings["rounding_power"],
        "general:gaps_in": settings["gaps_in"],
        "general:gaps_out": settings["gaps_out"],
        "decoration:blur:enabled": settings["blur"],
        "decoration:blur:size": settings["blur_size"],
        "decoration:blur:passes": settings["blur_passes"],
        "decoration:inactive_opacity": float(settings["inactive_opacity"]) / 100,
        "decoration:shadow:enabled": settings["shadow"],
        "input:sensitivity": settings["sensitivity"],
        "input:touchpad:natural_scroll": settings["natural_scroll"],
        "input:left_handed": settings["left_handed"],
        "input:touchpad:tap-to-click": settings["tap_to_click"],
        "input:touchpad:scroll_factor": float(settings["scroll_factor"]) / 100,
        "input:repeat_rate": settings["repeat_rate"],
        "input:repeat_delay": settings["repeat_delay"],
        "input:follow_mouse": settings["focus_follows_mouse"],
        "misc:vrr": 1 if settings["vrr"] else 0,
    }
    for option, value in values.items():
        keyword(option, value)
    apply_animations(settings)
    run(["hyprctl", "setcursor", os.environ.get("XCURSOR_THEME", "Bibata-Modern-Ice"), str(settings["cursor_size"])])
    if shutil.which("gsettings"):
        run(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", f"{float(settings['text_scale']) / 100:.2f}"])
    if shutil.which("powerprofilesctl"):
        run(["powerprofilesctl", "set", str(settings["power_profile"])], timeout=12)
    apply_idle_timeout(settings["idle_lock"])
    if THEME_BIN.exists() and settings.get("adaptive_color", True):
        run([str(THEME_BIN), str(settings["wallpaper"])], timeout=20)


def palette() -> dict:
    return {
        **{
            "background": "#121923", "surface": "#202b39", "surfaceRaised": "#2d3948",
            "text": "#eef5ff", "muted": "#9eabbc", "accent": "#7ebeff",
            "accent2": "#9a92ff", "border": "#b6d4ef", "danger": "#ff7482",
        },
        **read_json(CONFIG / "tempered/palette.json"),
    }


def sinks() -> list[tuple[str, str]]:
    raw = output(["pactl", "-f", "json", "list", "sinks"], "[]")
    try:
        records = json.loads(raw)
    except ValueError:
        return []
    return [(str(item.get("name", "")), str(item.get("description") or item.get("name", "Audio"))) for item in records]


def sources() -> list[tuple[str, str]]:
    raw = output(["pactl", "-f", "json", "list", "sources"], "[]")
    try:
        records = json.loads(raw)
    except ValueError:
        return []
    return [(str(item.get("name", "")), str(item.get("description") or item.get("name", "Microphone"))) for item in records if not str(item.get("name", "")).endswith(".monitor")]


class TemperedSettings(Adw.Application):
    def __init__(self, initial_page: str = "home") -> None:
        super().__init__(application_id="io.github.dsksnkz.TemperedOS.Settings")
        self.initial_page = initial_page
        self.settings = load()
        self.window: Adw.ApplicationWindow | None = None
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=180)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.toast_overlay = Adw.ToastOverlay(hexpand=True, vexpand=True)
        self._brightness_timeout = 0
        self._scale_timers: dict[str, int] = {}
        self._scale_commits: dict[str, Callable[[], bool]] = {}
        self.page_factories = {
            "home": self.profile_page, "wifi": self.wifi_page, "bluetooth": self.bluetooth_page,
            "network": self.network_page, "sound": self.sound_page, "power": self.power_page,
            "system": self.system_page, "access": self.accessibility_page, "acrylic": self.appearance_page,
            "island": self.island_page, "motion": self.motion_page, "displays": self.displays_page,
            "input": self.input_page, "apps": self.apps_page, "storage": self.storage_page,
            "region": self.region_page, "privacy": self.privacy_page,
        }
        self._pending_brightness = float(self.settings["display_brightness"])
        self.connect("activate", self.activate)

    def activate(self, *_args: object) -> None:
        if self.window:
            self.window.present()
            return
        self.install_css()
        window = Adw.ApplicationWindow(application=self, title="Tempered OS Settings")
        window.set_default_size(1040, 720)
        window.set_size_request(780, 560)
        window.add_css_class("tempered-window")
        window.connect("close-request", self.flush_preferences)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Tempered OS"))
        apply_button = Gtk.Button(label="Apply")
        apply_button.add_css_class("suggested-action")
        apply_button.set_tooltip_text("Apply all customization")
        apply_button.connect("clicked", lambda *_args: self.reapply())
        header.pack_end(apply_button)
        header.pack_end(self.header_button("view-refresh-symbolic", self.refresh_theme, "Refresh wallpaper colors"))
        toolbar.add_top_bar(header)

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        split.append(self.sidebar())
        self.toast_overlay.set_child(self.stack)
        split.append(self.toast_overlay)
        toolbar.set_content(split)
        window.set_content(toolbar)

        # Only build the page being used. Opening Settings must not probe every
        # monitor, audio device, Bluetooth adapter and disk before drawing a frame.
        self.window = window
        self.select_page(self.initial_page)
        self.nav.grab_focus()
        self.window = window
        window.present()

    def install_css(self) -> None:
        colors = palette()
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        adwaita_symbols = Path("/usr/share/icons/Adwaita/symbolic")
        if adwaita_symbols.is_dir():
            for category in adwaita_symbols.iterdir():
                if category.is_dir():
                    icon_theme.add_search_path(str(category))
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if colors.get("dark", True) else Adw.ColorScheme.FORCE_LIGHT
        )
        try:
            stylesheet = SETTINGS_CSS.read_text(encoding="utf-8")
        except OSError as error:
            print(f"Could not load {SETTINGS_CSS}: {error}", file=sys.stderr)
            stylesheet = ""
        provider = Gtk.CssProvider()
        provider.load_from_string(f'''@define-color tempered_bg {colors["background"]};
@define-color tempered_surface {colors["surface"]};
@define-color tempered_raised {colors["surfaceRaised"]};
@define-color tempered_text {colors["text"]};
@define-color tempered_muted {colors["muted"]};
@define-color tempered_accent {colors["accent"]};
@define-color tempered_accent_2 {colors["accent2"]};
@define-color tempered_border {colors["border"]};
@define-color tempered_danger {colors["danger"]};

{stylesheet}''')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def sidebar(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_size_request(230, -1)
        box.add_css_class("tempered-sidebar")
        mark = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        mark.set_margin_top(16); mark.set_margin_start(18); mark.set_margin_bottom(2)
        gear = Gtk.Image.new_from_icon_name("emblem-system-symbolic")
        gear.set_pixel_size(18)
        title = Gtk.Label(label="Settings", xalign=0); title.add_css_class("title-2")
        mark.append(gear); mark.append(title); box.append(mark)
        search = Gtk.SearchEntry(placeholder_text="Search")
        search.set_margin_start(12); search.set_margin_end(12); search.set_margin_bottom(4)
        box.append(search)
        nav = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.nav = nav
        nav.add_css_class("navigation-sidebar")
        entries = [
            ("home", str(self.settings.get("display_name") or getpass.getuser()), "avatar-default-symbolic"),
            ("wifi", "Wi-Fi", "network-wireless-symbolic"),
            ("bluetooth", "Bluetooth", "bluetooth-symbolic"),
            ("network", "Network", "network-wired-symbolic"),
            ("sound", "Sound", "audio-speakers-symbolic"),
            ("power", "Power and Battery", "battery-symbolic"),
            ("system", "General", "preferences-system-symbolic"),
            ("access", "Accessibility", "preferences-desktop-accessibility-symbolic"),
            ("acrylic", "Appearance", "applications-graphics-symbolic"),
            ("island", "Desktop and Island", "view-more-symbolic"),
            ("motion", "Motion and Windows", "preferences-system-windows-symbolic"),
            ("displays", "Displays", "video-display-symbolic"),
            ("input", "Keyboard and Pointer", "input-keyboard-symbolic"),
            ("apps", "Launcher and Apps", "system-software-install-symbolic"),
            ("storage", "Storage and Updates", "drive-harddisk-symbolic"),
            ("region", "Language and Time", "preferences-system-time-symbolic"),
            ("privacy", "Privacy and safety", "security-high-symbolic"),
        ]
        for name, label, icon in entries:
            row = Adw.ActionRow(title=label)
            row.set_name(name)
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            safe_icon = icon if icon_theme.has_icon(icon) else "preferences-system-symbolic"
            image = Gtk.Image.new_from_icon_name(safe_icon)
            image.set_pixel_size(16)
            row.add_prefix(image)
            nav.append(row)
        nav.connect("row-selected", lambda _list, row: self.select_page(row.get_name()) if row else None)
        nav.set_filter_func(lambda row: search.get_text().casefold() in row.get_title().casefold())
        search.connect("search-changed", lambda *_args: nav.invalidate_filter())
        nav_scroll = Gtk.ScrolledWindow(vexpand=True)
        nav_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nav_scroll.set_child(nav)
        box.append(nav_scroll)
        return box

    def page(self, title: str, description: str) -> tuple[Adw.PreferencesPage, Adw.PreferencesGroup]:
        page = Adw.PreferencesPage(title=title)
        group = Adw.PreferencesGroup(title=title)
        page.add(group)
        return page, group

    def select_page(self, name: str) -> None:
        if name not in self.page_factories:
            name = "home"
        if self.stack.get_child_by_name(name) is None:
            self.stack.add_named(self.page_factories[name](), name)
        self.stack.set_visible_child_name(name)
        index = 0
        while row := self.nav.get_row_at_index(index):
            if row.get_name() == name:
                self.nav.select_row(row)
                return
            index += 1

    def profile_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Home")
        hero_group = Adw.PreferencesGroup()
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        hero.add_css_class("tempered-hero")
        display_name = str(self.settings.get("display_name") or getpass.getuser())
        self.avatar = Adw.Avatar(size=76, text=display_name, show_initials=True)
        self.load_avatar()
        identity = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
        kicker = Gtk.Label(label="YOUR TEMPERED OS", xalign=0); kicker.add_css_class("section-kicker")
        self.profile_name = Gtk.Label(label=display_name, xalign=0, max_width_chars=28, ellipsize=Pango.EllipsizeMode.END); self.profile_name.add_css_class("title-1")
        detail = Gtk.Label(label="A space of your own.", xalign=0); detail.add_css_class("dim-label")
        identity.append(kicker); identity.append(self.profile_name); identity.append(detail)
        hero.append(self.avatar); hero.append(identity)
        hero_group.add(hero); page.add(hero_group)

        personal = Adw.PreferencesGroup(title="Personal")
        name_entry = Adw.EntryRow(title="Display name", text=display_name, show_apply_button=True)
        name_entry.connect("apply", lambda row: self.set_display_name(row.get_text()))
        personal.add(name_entry)
        self.action(personal, "Profile picture", "Only stored on this device", "avatar-default-symbolic", self.choose_avatar)
        self.action(personal, "Your desk", "Calendar, focus sessions and a private scratchpad", "user-home-symbolic",
                    lambda: detached([str(HOME / ".local/bin/tempered-control"), "desk"]))
        self.action(personal, "Shelf", "Captures, places, colors and your shortcuts", "folder-pictures-symbolic",
                    lambda: detached([str(HOME / ".local/bin/tempered-shelf")]))
        page.add(personal)

        overview = Adw.PreferencesGroup(title="At a glance")
        self.action(overview, "Appearance", "Wallpaper colors and acrylic", "applications-graphics-symbolic", lambda: self.select_page("acrylic"))
        self.action(overview, "Sound", "Speakers, IEMs and microphones", "audio-speakers-symbolic", lambda: self.select_page("sound"))
        profile = str(self.settings.get("power_profile", "balanced")).replace("-", " ").title()
        self.action(overview, "Power and Battery", profile, "battery-symbolic", lambda: self.select_page("power"))
        self.action(overview, "Displays", "Layout, refresh rate and brightness", "video-display-symbolic", lambda: self.select_page("displays"))
        page.add(overview)
        return page

    def load_avatar(self) -> None:
        path = Path(str(self.settings.get("profile_image", "")))
        if path.is_file():
            try:
                self.avatar.set_custom_image(Gdk.Texture.new_from_filename(str(path)))
            except GLib.Error:
                pass

    def set_display_name(self, name: str) -> None:
        name = name.strip()[:48] or getpass.getuser()
        self.change("display_name", name)
        self.profile_name.set_label(name)
        self.avatar.set_text(name)
        self.nav.get_row_at_index(0).set_title(name)
        self.toast("Your profile is saved")

    def choose_avatar(self) -> None:
        dialog = Gtk.FileDialog(title="Choose a profile picture")
        images = Gtk.FileFilter(); images.set_name("Images"); images.add_mime_type("image/*")
        filters = Gio.ListStore.new(Gtk.FileFilter); filters.append(images); dialog.set_filters(filters)
        dialog.open(self.window, None, self.avatar_chosen)

    def avatar_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            selected = dialog.open_finish(result)
        except GLib.Error:
            return
        if not selected.get_path():
            self.toast("Choose an image saved on this device")
            return
        try:
            from PIL import Image, ImageOps
            STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination = STATE / "profile.png"
            with Image.open(selected.get_path()) as image:
                photo = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (256, 256))
                photo.save(destination, "PNG")
            self.change("profile_image", str(destination))
            self.load_avatar()
            self.toast("Profile picture updated")
        except (OSError, ValueError, Image.DecompressionBombError):
            self.toast("Could not open that image")

    def switch(self, group: Adw.PreferencesGroup, key: str, title: str, subtitle: str, option: str | None = None) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle, active=bool(self.settings[key]))
        row.connect("notify::active", lambda widget, _param: self.change(key, widget.get_active(), lambda value: keyword(option, value) if option else None))
        group.add(row)
        return row

    def scale(self, group: Adw.PreferencesGroup, key: str, title: str, subtitle: str, minimum: float, maximum: float, step: float, apply: Callable[[float], None] | None = None) -> Gtk.Scale:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, minimum, maximum, step)
        slider.set_size_request(220, -1); slider.set_value(float(self.settings[key])); slider.set_draw_value(True)
        slider.connect("value-changed", lambda widget: self.delayed_change(key, widget.get_value(), apply))
        row.add_suffix(slider); group.add(row)
        return slider

    def choice(self, group: Adw.PreferencesGroup, key: str, title: str, subtitle: str, values: list[str], apply: Callable[[str], None] | None = None) -> Gtk.DropDown:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        dropdown = Gtk.DropDown.new_from_strings(values)
        current = str(self.settings.get(key, values[0])); dropdown.set_selected(values.index(current) if current in values else 0)
        dropdown.connect("notify::selected", lambda widget, _param: self.change(key, values[widget.get_selected()], apply))
        row.add_suffix(dropdown); group.add(row)
        return dropdown

    def action(self, group: Adw.PreferencesGroup, title: str, subtitle: str, icon: str, callback: Callable[[], None]) -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
        row.add_prefix(Gtk.Image.new_from_icon_name(icon)); row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda *_args: callback()); group.add(row)

    def device_picker(self, group: Adw.PreferencesGroup, title: str, subtitle: str,
                      labels: list[str], selected: int, callback: Callable[[int], None]) -> None:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class("tempered-device-card")
        title_label = Gtk.Label(label=title, xalign=0); title_label.add_css_class("heading")
        subtitle_label = Gtk.Label(label=subtitle, xalign=0); subtitle_label.add_css_class("dim-label")
        selector = Gtk.DropDown.new_from_strings(labels)
        selector.set_hexpand(True); selector.set_selected(selected)
        selector.connect("notify::selected", lambda widget, _param: callback(widget.get_selected()))
        card.append(title_label); card.append(subtitle_label); card.append(selector)
        group.add(card)

    def change(self, key: str, value: object, apply: Callable[[object], None] | None = None) -> None:
        self.settings[key] = value; save(self.settings, (key,))
        if apply:
            apply(value)

    def delayed_change(self, key: str, value: float, apply: Callable[[float], None] | None) -> None:
        value = round(value, 2)
        self.settings[key] = value
        if key in self._scale_timers:
            GLib.source_remove(self._scale_timers.pop(key))
        def commit() -> bool:
            self._scale_timers.pop(key, None)
            self._scale_commits.pop(key, None)
            save(self.settings, (key,))
            if apply:
                apply(value)
            return GLib.SOURCE_REMOVE
        self._scale_timers[key] = GLib.timeout_add(180, commit)
        self._scale_commits[key] = commit

    def flush_preferences(self, *_args) -> bool:
        for key, commit in list(self._scale_commits.items()):
            source = self._scale_timers.get(key)
            if source:
                GLib.source_remove(source)
            commit()
        if self._brightness_timeout:
            GLib.source_remove(self._brightness_timeout)
            self.commit_brightness()
        return False

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))

    def header_button(self, icon: str, callback: Callable[[], None], tooltip: str) -> Gtk.Button:
        button = Gtk.Button(icon_name=icon, tooltip_text=tooltip)
        button.connect("clicked", lambda *_args: callback())
        return button

    def appearance_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Appearance", "")
        self.action(group, "Wallpapers", "Browse local and online", "preferences-desktop-wallpaper-symbolic", lambda: detached([str(HOME / ".local/bin/tempered-wallpaper-picker")]))
        self.action(group, "Choose image", "Select a file", "folder-pictures-symbolic", self.choose_wallpaper)
        self.switch(group, "adaptive_color", "Wallpaper colors", "Regenerate the interface palette whenever the wallpaper changes")
        self.scale(group, "glass_opacity", "Glass density", "Lower is airier; higher separates controls from busy images", 45, 92, 1)
        self.scale(group, "rounding", "Corner character", "Shared by windows, menus and shell surfaces", 6, 28, 1, lambda value: keyword("decoration:rounding", round(value)))
        self.scale(group, "rounding_power", "Corner continuity", "Smoother G2-style corner curvature", 2, 4, 0.1, lambda value: keyword("decoration:rounding_power", value))
        self.switch(group, "blur", "Acrylic blur", "Blur transparent windows and Tempered shell layers", "decoration:blur:enabled")
        self.scale(group, "blur_size", "Blur reach", "How far the acrylic samples the wallpaper", 2, 16, 1, lambda value: keyword("decoration:blur:size", round(value)))
        self.scale(group, "blur_passes", "Blur refinement", "More passes look smoother and use more GPU", 1, 5, 1, lambda value: keyword("decoration:blur:passes", round(value)))
        return page

    def island_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Desktop and Island", "")
        self.scale(group, "island_width", "Island span", "Percentage of the monitor width", 38, 68, 1)
        self.scale(group, "island_height", "Island height", "Vertical size", 42, 76, 1)
        self.switch(group, "island_compact", "Compact current", "Tighten information when the display is crowded")
        self.switch(group, "show_seconds", "Show seconds", "Useful when timing work; calmer when disabled")
        self.switch(group, "music_visualizer", "Audio-reactive current", "Real audio levels while music is playing; nothing moving at idle")
        self.switch(group, "island_feedback", "Volume feedback", "Briefly show keyboard volume changes in the island")
        self.action(group, "Open the island", "Preview controls and current system state", "view-more-symbolic", lambda: detached(["qs", "ipc", "-p", shell_path(), "call", "tempered", "controls"]))
        self.action(group, "Restart shell", "Reload the island after a display or theme change", "view-refresh-symbolic", self.restart_shell)
        return page

    def displays_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Displays", "Keep the known-good 200 Hz path while exposing layout, brightness and variable refresh controls.")
        monitor = output(["hyprctl", "monitors", "-j"], "[]")
        try:
            records = json.loads(monitor); summary = " · ".join(f"{item['name']}  {item['width']}×{item['height']}  {round(item['refreshRate'])} Hz" for item in records)
        except (ValueError, KeyError, TypeError):
            summary = "Display information unavailable"
        brightness = output([str(HOME / ".local/bin/tempered-brightness"), "get"])
        if brightness.isdigit():
            self.settings["display_brightness"] = int(brightness)
        self.action(group, "Connected displays", summary, "video-display-symbolic", lambda: detached(["wdisplays"]))
        self.scale(group, "display_brightness", "Brightness", "Uses DDC/CI for external monitors and backlight controls for laptop panels", 1, 100, 1, self.set_brightness)
        self.switch(group, "vrr", "Variable refresh rate", "Off is the compatible default for this hybrid GPU path", "misc:vrr")
        self.action(group, "Night light", "Color temperature and schedule", "weather-clear-night-symbolic", lambda: detached(["hyprsunset"]))
        self.action(group, "Color information", "Inspect HDR, color space and connector state", "applications-graphics-symbolic", lambda: detached(["kitty", "--title", "Display state", "-e", "hyprctl", "monitors", "all"]))
        return page

    def sound_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Sound", "Outputs and microphones are explicit, so Bluetooth and IEM routes do not silently steal each other.")
        current_volume = output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        match = re.search(r"([0-9.]+)", current_volume)
        if match:
            self.settings["output_volume"] = round(float(match.group(1)) * 100)
        self.scale(group, "output_volume", "Output volume", "Current default output", 0, 125, 1, lambda value: run(["wpctl", "set-volume", "-l", "1.25", "@DEFAULT_AUDIO_SINK@", f"{round(value)}%"]))
        sink_values = sinks()
        if sink_values:
            names = [self.friendly_device_name(identifier, label) for identifier, label in sink_values]
            default_sink = output(["pactl", "get-default-sink"])
            selected = next((index for index, item in enumerate(sink_values) if item[0] == default_sink), 0)
            self.device_picker(group, "Sound output", "Speakers, IEMs or Bluetooth", names, selected,
                               lambda index: run(["pactl", "set-default-sink", sink_values[index][0]]))
        source_values = sources()
        if source_values:
            labels = [self.friendly_device_name(identifier, label) for identifier, label in source_values]
            default_source = output(["pactl", "get-default-source"])
            selected = next((index for index, item in enumerate(source_values) if item[0] == default_source), 0)
            self.device_picker(group, "Microphone", "Choose the recording input", labels, selected,
                               lambda index: run(["pactl", "set-default-source", source_values[index][0]]))
        self.settings["mic_muted"] = "MUTED" in output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]) 
        self.switch(group, "mic_muted", "Mute microphone", "Stops the current default input", None).connect("notify::active", lambda row, _p: run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1" if row.get_active() else "0"]))
        self.action(group, "Advanced sound", "Per-app routing, profiles and channel balance", "audio-card-symbolic", lambda: detached(["pavucontrol"]))
        return page

    def input_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Keyboard and pointer", "Tune the physical feel without hiding the actual values.")
        self.scale(group, "sensitivity", "Pointer sensitivity", "Hyprland acceleration offset", -1.0, 1.0, 0.05, lambda value: keyword("input:sensitivity", value))
        self.switch(group, "natural_scroll", "Natural scrolling", "Move content in the same direction as your fingers", "input:touchpad:natural_scroll")
        self.switch(group, "left_handed", "Left-handed pointer", "Swap the primary and secondary buttons", "input:left_handed")
        self.switch(group, "tap_to_click", "Tap to click", "Touchpad taps act as button presses", "input:touchpad:tap-to-click")
        self.scale(group, "scroll_factor", "Scroll distance", "Touchpad scroll multiplier", 25, 200, 5, lambda value: keyword("input:touchpad:scroll_factor", value / 100))
        self.scale(group, "repeat_rate", "Key repeat rate", "Characters per second while holding a key", 15, 60, 1, lambda value: keyword("input:repeat_rate", round(value)))
        self.scale(group, "repeat_delay", "Key repeat delay", "Milliseconds before repetition begins", 180, 900, 10, lambda value: keyword("input:repeat_delay", round(value)))
        return page

    def motion_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Motion and windows", "Fast intent, gentle arrival. Every spatial change should explain where content went.")
        self.switch(group, "animations", "Window motion", "Animate windows, workspaces and layers").connect("notify::active", lambda *_args: apply_animations(self.settings))
        self.switch(group, "reduce_motion", "Reduce motion", "Disable spatial travel while preserving color feedback").connect("notify::active", lambda *_args: apply_animations(self.settings))
        self.scale(group, "animation_speed", "Motion pace", "50 is unhurried; 200 is immediate", 50, 200, 5, lambda _value: apply_animations(self.settings))
        self.scale(group, "gaps_in", "Inner breathing room", "Space between tiled windows", 0, 20, 1, lambda value: keyword("general:gaps_in", round(value)))
        self.scale(group, "gaps_out", "Outer breathing room", "Space around each workspace", 0, 30, 1, lambda value: keyword("general:gaps_out", round(value)))
        self.scale(group, "inactive_opacity", "Inactive window presence", "Keep background work visible without competing", 75, 100, 1, lambda value: keyword("decoration:inactive_opacity", value / 100))
        self.switch(group, "shadow", "Depth shadows", "Separate overlapping acrylic planes", "decoration:shadow:enabled")
        self.choice(group, "focus_follows_mouse", "Focus behavior", "Choose how pointer movement changes focus", ["0", "1", "2", "3"], lambda value: keyword("input:follow_mouse", value))
        return page

    def wifi_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Wi-Fi", "")
        wifi = output(["nmcli", "radio", "wifi"], "disabled") == "enabled"
        self.settings["wifi"] = wifi
        self.switch(group, "wifi", "Wi‑Fi", "Wireless networking", None).connect("notify::active", lambda row, _p: run(["nmcli", "radio", "wifi", "on" if row.get_active() else "off"]))
        active = output(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
        current = next((line.split(":", 1)[1] for line in active.splitlines() if line.startswith("yes:")), "Not connected")
        self.action(group, "Current network", current, "network-wireless-symbolic", lambda: detached(["qs", "ipc", "-p", shell_path(), "call", "tempered", "wifi"]))
        self.action(group, "Known networks", "Saved connections", "emblem-system-symbolic", lambda: detached(["nm-connection-editor"]))
        return page

    def bluetooth_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Bluetooth", "")
        bluetooth = "Powered: yes" in output(["bluetoothctl", "show"])
        self.settings["bluetooth"] = bluetooth
        self.switch(group, "bluetooth", "Bluetooth", "Headphones, controllers and nearby devices", None).connect("notify::active", lambda row, _p: run(["bluetoothctl", "power", "on" if row.get_active() else "off"]))
        devices = output(["bluetoothctl", "devices", "Connected"])
        summary = " · ".join(line.split(" ", 2)[2] for line in devices.splitlines() if len(line.split(" ", 2)) == 3) or "No connected devices"
        self.action(group, "Devices", summary, "bluetooth-symbolic", lambda: detached(["qs", "ipc", "-p", shell_path(), "call", "tempered", "bluetooth"]))
        return page

    def network_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Network", "")
        self.action(group, "Connections", "Ethernet, DNS and saved networks", "network-wired-symbolic", lambda: detached(["nm-connection-editor"]))
        self.action(group, "Connection status", output(["nmcli", "-t", "-f", "STATE", "general"], "Unknown"), "network-transmit-receive-symbolic", lambda: detached(["kitty", "--title", "Network status", "-e", "nmcli", "device", "status"]))
        return page

    def power_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Power and idle", "Performance when requested; a calm baseline everywhere else.")
        active_profile = output(["powerprofilesctl", "get"])
        if active_profile in {"power-saver", "balanced", "performance"}:
            self.settings["power_profile"] = active_profile
        self.choice(group, "power_profile", "Power mode", "Changes CPU and platform policy", ["power-saver", "balanced", "performance"], lambda value: run(["powerprofilesctl", "set", value], timeout=12))
        self.scale(group, "idle_lock", "Lock after", "Seconds of inactivity before locking", 120, 3600, 60, apply_idle_timeout)
        self.action(group, "Battery and processes", "Inspect energy use and background load", "utilities-system-monitor-symbolic", lambda: detached(["missioncenter"]))
        self.action(group, "Suspend now", "Lock first, then enter sleep", "media-playback-pause-symbolic", lambda: detached(["sh", "-lc", "hyprlock & sleep 0.4; systemctl suspend"]))
        return page

    def apps_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Apps and startup", "Applications stay inspectable: what opens files, what starts with the session, and what may be removed.")
        browser = output(["xdg-settings", "get", "default-web-browser"], "System default")
        self.action(group, "Installed applications", "Browse, search and uninstall through Orbit Apps", "system-software-install-symbolic", lambda: detached(["orbitos-apps"]))
        self.action(group, "Default browser", browser, "web-browser-symbolic", lambda: detached(["kitty", "--title", "Default applications", "-e", "bash", "-lc", "xdg-settings get default-web-browser; echo; echo 'Use xdg-settings set default-web-browser NAME.desktop to change it.'; read -r -p 'Press Enter to close…'"]))
        self.action(group, "Startup services", "Review everything enabled for your user session", "system-run-symbolic", lambda: detached(["kitty", "--title", "Startup services", "-e", "bash", "-lc", "systemctl --user list-unit-files --state=enabled; echo; read -r -p 'Press Enter to close…'"]))
        self.action(group, "Flatpak permissions", "Files, devices, cameras and background access", "application-x-addon-symbolic", lambda: detached(["flatseal"]))
        return page

    def storage_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Storage and updates", "Know what occupies the machine and keep packages current without hiding privileged changes.")
        usage = shutil.disk_usage("/")
        used = round((usage.total - usage.free) / usage.total * 100)
        free_gib = usage.free / 1024 ** 3
        self.action(group, "System disk", f"{used}% used · {free_gib:.1f} GiB available", "drive-harddisk-symbolic", lambda: detached(["baobab"]))
        self.action(group, "Disks and partitions", "Devices, SMART health and mounted volumes", "drive-removable-media-symbolic", lambda: detached(["gnome-disks"]))
        self.action(group, "Software update", "Review a complete Arch upgrade in a terminal", "software-update-available-symbolic", lambda: detached(["kitty", "--title", "Tempered update", "-e", "bash", "-lc", "sudo pacman -Syu; status=$?; echo; read -r -p 'Press Enter to close…'; exit $status"]))
        self.action(group, "Package cache", "Keep the two newest cached package versions", "user-trash-symbolic", lambda: detached(["kitty", "--title", "Package cache", "-e", "bash", "-lc", "echo 'This removes older cached package versions.'; read -r -p 'Continue? [y/N] ' answer; [[ $answer =~ ^[Yy]$ ]] && sudo paccache -rk2; echo; read -r -p 'Press Enter to close…'"]))
        return page

    def region_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Language and time", "Locale, clock and identity come from the system rather than a private shell database.")
        locale = output(["sh", "-lc", "printf %s \"${LANG:-C}\""], "C")
        timezone = output(["timedatectl", "show", "--property=Timezone", "--value"], "Unknown timezone")
        hostname = output(["hostnamectl", "hostname"], "Unknown host")
        self.action(group, "Language and formats", locale, "preferences-desktop-locale-symbolic", lambda: detached(["kitty", "--title", "Locale", "-e", "bash", "-lc", "localectl status; echo; echo 'Edit /etc/locale.gen and run locale-gen to add locales.'; read -r -p 'Press Enter to close…'"]))
        self.action(group, "Date and time", timezone, "preferences-system-time-symbolic", lambda: detached(["kitty", "--title", "Date and time", "-e", "bash", "-lc", "timedatectl; echo; echo 'Use sudo timedatectl set-timezone AREA/CITY to change the zone.'; read -r -p 'Press Enter to close…'"]))
        self.action(group, "Device name", hostname, "computer-symbolic", lambda: detached(["kitty", "--title", "Device name", "-e", "bash", "-lc", "hostnamectl status; echo; echo 'Use sudo hostnamectl hostname NAME to rename this device.'; read -r -p 'Press Enter to close…'"]))
        return page

    def accessibility_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Accessibility", "Make the interface easier to read and control without creating a separate visual language.")
        self.scale(group, "cursor_size", "Pointer size", "Applied to the active Hyprland cursor", 16, 64, 1, lambda value: run(["hyprctl", "setcursor", os.environ.get("XCURSOR_THEME", "Bibata-Modern-Ice"), str(round(value))]))
        self.scale(group, "text_scale", "Text scale", "GTK application text size", 80, 180, 5, lambda value: run(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", f"{value / 100:.2f}"]))
        self.action(group, "Keyboard accessibility", "Inspect current input devices and repeat behavior", "input-keyboard-symbolic", lambda: detached(["kitty", "--title", "Input devices", "-e", "bash", "-lc", "hyprctl devices; echo; read -r -p 'Press Enter to close…'"]))
        self.action(group, "Workspace navigation", "Super + wheel switches spaces; add Shift to move a window", "view-grid-symbolic", lambda: self.toast("Your existing workspace shortcuts are unchanged"))
        return page

    def privacy_page(self) -> Adw.PreferencesPage:
        page, group = self.page("Privacy and safety", "Visible controls for capture, notifications and session security.")
        dnd = output(["swaync-client", "--skip-wait", "-D"], "false") == "true"
        self.settings["dnd"] = dnd
        self.switch(group, "dnd", "Do Not Disturb", "Silence notification banners while retaining history", None).connect(
            "notify::active",
            lambda row, _p: run(["swaync-client", "--skip-wait", "--dnd-on" if row.get_active() else "--dnd-off"]),
        )
        self.action(group, "Lock screen", "Secure this session immediately", "system-lock-screen-symbolic", lambda: detached(["hyprlock"]))
        self.action(group, "Screenshot", "Select an area and copy it", "applets-screenshooter-symbolic", lambda: detached(["tempered-capture"]))
        self.action(group, "App permissions", "Flatpak cameras, microphones, files and devices", "application-x-addon-symbolic", lambda: detached(["flatseal"]))
        ufw_enabled = output(["sh", "-lc", "sed -n 's/^ENABLED=//p' /etc/ufw/ufw.conf 2>/dev/null"], "unknown")
        firewall = "Enabled" if ufw_enabled == "yes" else "Disabled" if ufw_enabled == "no" else "Status requires administrator access"
        self.action(group, "Firewall", firewall, "security-high-symbolic", lambda: detached(["kitty", "--title", "Firewall", "-e", "bash", "-lc", "sudo ufw status verbose; echo; read -r -p 'Press Enter to close…'"]))
        return page

    def system_page(self) -> Adw.PreferencesPage:
        page, group = self.page("System", "The machine beneath the material.")
        kernel = output(["uname", "-r"], "Unknown kernel")
        hypr = output(["hyprctl", "version"], "Hyprland").splitlines()[0]
        self.action(group, "Software", f"Arch Linux · {kernel}", "computer-symbolic", lambda: detached(["kitty", "-e", "bash", "-lc", "fastfetch; read -n1"]))
        self.action(group, "Compositor", hypr, "preferences-system-windows-symbolic", lambda: detached(["kitty", "-e", "hyprctl", "systeminfo"]))
        self.action(group, "Installed apps", "View or uninstall software with Orbit Apps", "system-software-install-symbolic", lambda: detached(["orbitos-apps"]))
        self.action(group, "Logs", "Follow user-session errors", "text-x-generic-symbolic", lambda: detached(["kitty", "--title", "Tempered logs", "-e", "journalctl", "--user", "-f"]))
        self.action(group, "Reapply settings", "Restore every saved runtime value", "emblem-ok-symbolic", self.reapply)
        return page

    def choose_wallpaper(self) -> None:
        dialog = Gtk.FileDialog(title="Choose the material source")
        images = Gtk.FileFilter(); images.set_name("Images"); images.add_mime_type("image/*")
        filters = Gio.ListStore.new(Gtk.FileFilter); filters.append(images); dialog.set_filters(filters)
        dialog.open(self.window, None, self.wallpaper_chosen)

    def wallpaper_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            selected = dialog.open_finish(result)
        except GLib.Error:
            return
        path = selected.get_path()
        if not path:
            return
        helper = HOME / ".local/bin/tempered-wallpaper-apply"
        result = run([str(helper), path], timeout=24)
        if result and result.returncode == 0:
            self.settings = load()
            self.toast("Wallpaper applied")
        else:
            self.toast("Could not apply that wallpaper")

    def refresh_theme(self) -> None:
        result = run([str(THEME_BIN), str(self.settings["wallpaper"])], timeout=20)
        if result and result.returncode == 0:
            self.toast("Palette drawn from wallpaper")
            GLib.timeout_add(400, lambda: (self.restart_shell(), GLib.SOURCE_REMOVE)[1])
        else:
            self.toast("Could not read that wallpaper")

    def restart_shell(self) -> None:
        run(["quickshell", "kill", "--path", shell_path()], timeout=4)
        detached(["quickshell", "--daemonize", "--path", shell_path()])
        self.toast("Dynamic island restarted")

    def set_brightness(self, value: float) -> None:
        self._pending_brightness = value
        if self._brightness_timeout:
            GLib.source_remove(self._brightness_timeout)
        self._brightness_timeout = GLib.timeout_add(280, self.commit_brightness)

    def commit_brightness(self) -> bool:
        self._brightness_timeout = 0
        helper = HOME / ".local/bin/tempered-brightness"
        detached([str(helper), "set", str(round(self._pending_brightness))])
        return GLib.SOURCE_REMOVE

    @staticmethod
    def friendly_device_name(identifier: str, label: str) -> str:
        if "Speaker__sink" in identifier:
            return "Built-in speakers"
        if "Headset__source" in identifier:
            return "Headset microphone"
        if "__Mic" in identifier:
            return "Built-in microphone"
        if identifier.startswith("bluez_"):
            return label.split(" - ", 1)[0]
        if identifier.endswith(".hdmi-stereo"):
            return "External monitor · HDMI"
        cleaned = re.sub(r"\s+", " ", label).strip()
        cleaned = re.sub(r"^500 Series Chipset Family HD Audio ", "", cleaned)
        cleaned = cleaned.replace("High Definition Audio Controller ", "")
        cleaned = cleaned.replace("HDMI / DisplayPort", "DisplayPort")
        return cleaned if len(cleaned) <= 42 else cleaned[:39].rstrip() + "…"

    def reapply(self) -> None:
        apply_all(self.settings); self.toast("Saved settings reapplied")


def main() -> int:
    settings = load()
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        apply_all(settings)
        return 0
    initial_page = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--page" else "home"
    app = TemperedSettings(initial_page)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
