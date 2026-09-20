#!/usr/bin/env python3
"""Tempered Shelf: captures, places, screen colors and a shortcut reference."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
from PIL import Image, ImageOps

from shelf_core import CONFIG, HOME, ShelfStore, captures, read_json, screenshot_directory, shortcuts, user_directory

CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "tempered-os/shelf"
PALETTE = {"background": "#0c141a", "surface": "#19262e", "surfaceRaised": "#2a3a43",
           "text": "#f0f4f6", "muted": "#acbfc9", "accent": "#a3ccda", "border": "#71858d"}


def thumbnail(source: Path, size=420) -> Path:
    stat = source.stat()
    key = hashlib.sha256(f"{source}:{stat.st_mtime_ns}:{stat.st_size}:{size}".encode()).hexdigest()
    target = CACHE / (key + ".png")
    if target.is_file():
        return target
    CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with Image.open(source) as original:
        picture = ImageOps.exif_transpose(original)
        picture.thumbnail((size, size), Image.Resampling.LANCZOS)
        picture.save(target, "PNG")
    target.chmod(0o600)
    return target


def label(text, css="", **kwargs):
    widget = Gtk.Label(label=text, xalign=0, **kwargs)
    if css:
        widget.add_css_class(css)
    return widget


def button(text, callback, icon=None, css=None):
    widget = Gtk.Button()
    if icon:
        box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        box.append(Gtk.Image.new_from_icon_name(icon))
        box.append(Gtk.Label(label=text))
        widget.set_child(box)
    else:
        widget.set_label(text)
    if css:
        widget.add_css_class(css)
    widget.connect("clicked", lambda *_: callback())
    return widget


def clear(box):
    child = box.get_first_child()
    while child:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


class Shelf(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.dsksnkz.TemperedOS.Shelf",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.store = ShelfStore()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tempered-shelf")
        self.generation = 0
        self.busy = False
        self.stopped = False
        self.timer = 0
        self.monitor = None
        self.palette_monitor = None
        self.palette_timer = 0
        self.actions = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tempered-shelf-action")

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        allowed = {"--captures": "captures", "--places": "places", "--colors": "colors", "--shortcuts": "shortcuts"}
        if any(arg not in allowed for arg in args):
            command_line.printerr("Usage: tempered-shelf [--captures|--places|--colors|--shortcuts]\n")
            return 2
        self.activate()
        if args:
            self.stack.set_visible_child_name(allowed[args[0]])
        return 0

    def do_shutdown(self):
        self.stopped = True
        if self.timer:
            GLib.source_remove(self.timer)
        if self.monitor:
            self.monitor.cancel()
        if self.palette_monitor:
            self.palette_monitor.cancel()
        if self.palette_timer:
            GLib.source_remove(self.palette_timer)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.actions.shutdown(wait=False, cancel_futures=True)
        Adw.Application.do_shutdown(self)

    def work(self, function, done, *, action=False):
        future = (self.actions if action else self.executor).submit(function)
        def complete(result):
            try:
                value, error = result.result(), None
            except Exception as exception:
                value, error = None, exception
            def dispatch():
                if not self.stopped:
                    done(value, error)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(dispatch)
        future.add_done_callback(complete)

    def toast(self, message):
        self.toasts.add_toast(Adw.Toast(title=str(message)[:220], timeout=5))

    def css(self):
        saved = read_json(CONFIG / "tempered/palette.json", {})
        colors = {**PALETTE, **(saved if isinstance(saved, dict) else {})}
        for key, fallback in PALETTE.items():
            if not isinstance(colors.get(key), str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", colors[key]):
                colors[key] = fallback
        self.colors = colors
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        symbols = Path("/usr/share/icons/Adwaita/symbolic")
        if symbols.is_dir():
            existing = set(theme.get_search_path())
            for category in symbols.iterdir():
                if category.is_dir() and str(category) not in existing:
                    theme.add_search_path(str(category))
        if hasattr(self, "provider"):
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self.provider)
        self.provider = Gtk.CssProvider()
        definitions = "\n".join(f"@define-color shelf_{key} {colors[key]};" for key in PALETTE)
        self.provider.load_from_string(definitions + "\n" + Path(__file__).with_name("shelf.css").read_text())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.css()
        self.window = Adw.ApplicationWindow(application=self, title="Tempered Shelf", default_width=1040, default_height=760)
        self.window.add_css_class("tempered-shelf")
        self.toasts = Adw.ToastOverlay()
        self.window.set_content(self.toasts)
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toasts.set_child(main)
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Shelf", subtitle="Tempered OS"))
        header.pack_end(button("Open folder", lambda: self.open_path(screenshot_directory()), "folder-open-symbolic"))
        main.append(header)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        hero.add_css_class("shelf-hero")
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, hexpand=True)
        titles.append(label("Keep it close.", "title-1"))
        titles.append(label("Captures, places and colors. Yours, on this device.", "dim-label", wrap=True))
        hero.append(titles)
        self.count_label = label("", "dim-label")
        hero.append(self.count_label)
        main.append(hero)

        self.stack = Gtk.Stack(vexpand=True, hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                               transition_duration=140)
        settings = read_json(CONFIG / "tempered/settings.json", {}) or {}
        if settings.get("reduce_motion") or settings.get("animations") is False:
            self.stack.set_transition_duration(0)
        switcher = Gtk.StackSwitcher(stack=self.stack, halign=Gtk.Align.CENTER)
        switcher.add_css_class("shelf-tabs")
        main.append(switcher)
        self.search = Gtk.SearchEntry(placeholder_text="Search this page", hexpand=True)
        self.search.set_margin_start(28); self.search.set_margin_end(28)
        self.search.set_margin_top(16); self.search.set_margin_bottom(8)
        self.search.connect("search-changed", self.search_changed)
        main.append(self.search)
        main.append(self.stack)
        self.stack.add_titled(self.captures_page(), "captures", "Captures")
        self.stack.add_titled(self.places_page(), "places", "Places")
        self.stack.add_titled(self.colors_page(), "colors", "Colors")
        self.stack.add_titled(self.shortcuts_page(), "shortcuts", "Shortcuts")
        self.stack.connect("notify::visible-child-name", self.page_changed)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.key_pressed)
        self.window.add_controller(keys)
        self.watch_captures()
        self.watch_palette()
        self.refresh_captures()
        self.refresh_places()
        self.refresh_colors()
        self.refresh_shortcuts()
        self.window.present()
        if self.store.error:
            self.toast(self.store.error)

    def key_pressed(self, controller, keyval, keycode, state):
        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_f:
            self.search.grab_focus(); return True
        if state & Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_r:
            self.refresh_captures(); self.refresh_shortcuts(); self.refresh_places(); return True
        return False

    def page_changed(self, *_):
        self.search.set_text("")
        self.count_label.set_label("")
        if self.stack.get_visible_child_name() == "captures":
            self.refresh_captures()
        elif self.stack.get_visible_child_name() == "shortcuts":
            self.refresh_shortcuts()

    def search_changed(self, *_):
        page = self.stack.get_visible_child_name()
        if page == "captures":
            self.flow.invalidate_filter()
        elif page == "places":
            self.refresh_places()
        elif page == "shortcuts":
            self.refresh_shortcuts()
        elif page == "colors":
            self.refresh_colors()

    def body(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(28); box.set_margin_end(28)
        box.set_margin_top(12); box.set_margin_bottom(24)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=box)
        return scroller, box

    def captures_page(self):
        scroller, box = self.body()
        toolbar = Gtk.Box(spacing=10)
        self.capture_mode = Gtk.DropDown.new_from_strings(["Select area", "Select window", "This display", "All displays"])
        self.capture_mode.set_tooltip_text("What to capture")
        self.delay = Gtk.DropDown.new_from_strings(["No delay", "3 seconds", "5 seconds", "10 seconds"])
        self.delay.set_tooltip_text("Wait before capturing; for area/window selection the wait happens first")
        self.capture_button = button("Capture", self.start_capture, "camera-photo-symbolic", "suggested-action")
        toolbar.append(self.capture_mode); toolbar.append(self.delay); toolbar.append(self.capture_button)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(button("Refresh", self.refresh_captures, "view-refresh-symbolic"))
        box.append(toolbar)
        self.capture_status = label("Saved locally and copied to your clipboard. Esc cancels selection.", "dim-label", wrap=True)
        box.append(self.capture_status)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12,
                                min_children_per_line=1, max_children_per_line=4, homogeneous=True)
        self.flow.set_filter_func(lambda child: self.search.get_text().casefold() in getattr(child, "search_text", ""))
        box.append(self.flow)
        self.empty_captures = Adw.StatusPage(title="Your next capture starts here", description="Choose an area, window or display above.", icon_name="camera-photo-symbolic")
        box.append(self.empty_captures)
        return scroller

    def watch_captures(self):
        folder = screenshot_directory()
        # A monitor on an existing directory needs no idle polling and reads no other folders.
        if folder.is_dir() and not self.monitor:
            try:
                self.monitor = Gio.File.new_for_path(str(folder)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                self.monitor.connect("changed", lambda *_: self.schedule_refresh())
            except GLib.Error:
                pass

    def watch_palette(self):
        folder = CONFIG / "tempered"
        if not folder.is_dir():
            return
        def changed(monitor, file, other, event):
            if file.get_basename() != "palette.json" and (other is None or other.get_basename() != "palette.json"):
                return
            if self.palette_timer:
                GLib.source_remove(self.palette_timer)
            def refresh():
                self.palette_timer = 0
                self.css(); self.refresh_colors()
                return GLib.SOURCE_REMOVE
            self.palette_timer = GLib.timeout_add(200, refresh)
        self.palette_monitor = Gio.File.new_for_path(str(folder)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.palette_monitor.connect("changed", changed)

    def schedule_refresh(self):
        if self.timer:
            GLib.source_remove(self.timer)
        def settled():
            self.timer = 0
            self.refresh_captures()
            return GLib.SOURCE_REMOVE
        self.timer = GLib.timeout_add(350, settled)

    def refresh_captures(self, *_):
        self.generation += 1
        generation = self.generation
        def list_done(paths, error):
            if generation != self.generation:
                return
            if error:
                self.toast(f"Cannot read captures: {error}"); return
            clear(self.flow)
            self.empty_captures.set_visible(not paths)
            if self.stack.get_visible_child_name() == "captures":
                self.count_label.set_label(f"{len(paths)} recent captures")
            for path in paths:
                self.add_capture(path, generation)
        self.work(captures, list_done)

    def add_capture(self, path, generation):
        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tile.add_css_class("capture-card")
        picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, height_request=140)
        opener = Gtk.Button(child=picture, tooltip_text="Preview " + path.name)
        opener.add_css_class("flat")
        opener.connect("clicked", lambda *_: self.preview(path))
        tile.append(opener)
        caption = label(path.name, "caption", ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=25)
        caption.set_margin_start(10); caption.set_margin_end(10); caption.set_margin_bottom(10)
        tile.append(caption)
        child = Gtk.FlowBoxChild(child=tile)
        child.search_text = path.name.casefold()
        self.flow.insert(child, -1)
        def ready(result, error):
            if generation != self.generation:
                return
            if error:
                opener.set_tooltip_text("This image cannot be previewed: " + path.name)
            else:
                picture.set_filename(str(result))
        self.work(lambda: thumbnail(path), ready)

    def start_capture(self):
        if self.busy:
            return
        mode = ("area", "window", "screen", "all")[self.capture_mode.get_selected()]
        delay = (0, 3, 5, 10)[self.delay.get_selected()]
        command = [sys.executable, str(Path(__file__).with_name("capture.py")), mode, "--delay", str(delay), "--quiet"]
        def done(result, error):
            if error:
                self.toast(error)
            elif result.returncode == 130:
                self.toast("Capture cancelled")
            elif result.returncode:
                self.toast(result.stderr.strip() or "Capture failed")
            else:
                self.toast(result.stderr.strip() or "Saved and copied")
                self.watch_captures(); self.refresh_captures()
        self.hidden_operation(command, done)

    def hidden_operation(self, command, done):
        self.busy = True
        self.hold()
        self.window.set_visible(False)
        def start():
            def finish(result, error):
                self.busy = False
                self.window.present()
                done(result, error)
                self.release()
            self.work(lambda: subprocess.run(command, capture_output=True, text=True, timeout=150), finish, action=True)
            return GLib.SOURCE_REMOVE
        # Let the app and its compositor closing animation leave the capture.
        GLib.timeout_add(350, start)

    def preview(self, path):
        dialog = Adw.Dialog(title=path.name, content_width=840, content_height=620)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Capture", subtitle=path.name))
        body.append(header)
        picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, vexpand=True)
        picture.set_margin_start(16); picture.set_margin_end(16)
        body.append(picture)
        self.work(lambda: thumbnail(path, 1800), lambda result, error: self.toast(error) if error else picture.set_filename(str(result)))
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, margin_bottom=16)
        actions.append(button("Copy image", lambda: self.copy_image(path), "edit-copy-symbolic", "suggested-action"))
        actions.append(button("Open", lambda: self.open_path(path), "document-open-symbolic"))
        actions.append(button("Folder", lambda: self.open_path(path.parent), "folder-open-symbolic"))
        actions.append(button("Pin", lambda: self.pin_path(path), "view-pin-symbolic"))
        actions.append(button("Trash", lambda: self.trash_capture(path, dialog), "user-trash-symbolic"))
        body.append(actions)
        dialog.set_child(body)
        dialog.present(self.window)

    def copy_image(self, path):
        def copy():
            # Normalize JPG/WebP too; the clipboard format always matches the bytes.
            import io
            with Image.open(path) as image:
                payload = io.BytesIO()
                image.save(payload, "PNG")
            subprocess.run(["wl-copy", "--type", "image/png"], input=payload.getvalue(), timeout=5, check=True, capture_output=True)
        self.work(copy, lambda _, error: self.toast(error or "Image copied"), action=True)

    def trash_capture(self, path, parent):
        confirm = Adw.AlertDialog(heading="Move capture to Trash?", body="You can restore it from your file manager. Pinned items are not deleted automatically.")
        confirm.add_response("cancel", "Keep"); confirm.add_response("trash", "Move to Trash")
        confirm.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.set_default_response("cancel"); confirm.set_close_response("cancel")
        def decided(dialog, result):
            if dialog.choose_finish(result) != "trash":
                return
            def finished(file, outcome):
                try:
                    file.trash_finish(outcome)
                    parent.close(); self.refresh_captures(); self.toast("Moved to Trash — recoverable in Files")
                except GLib.Error as error:
                    self.toast(error)
            Gio.File.new_for_path(str(path)).trash_async(GLib.PRIORITY_DEFAULT, None, finished)
        confirm.choose(parent, None, decided)

    def open_path(self, path):
        path = Path(path)
        if not path.exists():
            self.toast("This item is not available. It may have moved or be on a disconnected drive.")
            return
        def finished(source, result):
            try:
                Gio.AppInfo.launch_default_for_uri_finish(result)
            except GLib.Error as error:
                self.toast(error)
        Gio.AppInfo.launch_default_for_uri_async(path.as_uri(), None, None, finished)

    def places_page(self):
        scroller, box = self.body()
        actions = Gtk.Box(spacing=10)
        actions.append(button("Pin folder", lambda: self.choose_place(True), "folder-new-symbolic", "suggested-action"))
        actions.append(button("Pin file", lambda: self.choose_place(False), "list-add-symbolic"))
        box.append(actions)
        self.places_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(self.places_list)
        box.append(label("Unpinning only removes the shortcut. Your files stay where they are.", "dim-label", wrap=True))
        return scroller

    def choose_place(self, folder):
        dialog = Gtk.FileDialog(title="Pin a folder" if folder else "Pin a file")
        def selected(source, result):
            try:
                item = source.select_folder_finish(result) if folder else source.open_finish(result)
                if item and item.get_path():
                    self.pin_path(Path(item.get_path()))
            except GLib.Error:
                pass
        if folder:
            dialog.select_folder(self.window, None, selected)
        else:
            dialog.open(self.window, None, selected)

    def pin_path(self, path):
        try:
            added = self.store.pin(path)
            self.refresh_places(); self.toast("Pinned to Places" if added else "Already pinned")
        except (OSError, ValueError) as error:
            self.toast(error)

    def unpin(self, identity):
        try:
            self.store.unpin(identity); self.refresh_places(); self.toast("Unpinned — original file unchanged")
        except OSError as error:
            self.toast(error)

    def refresh_places(self):
        clear(self.places_list)
        needle = self.search.get_text().casefold() if self.stack.get_visible_child_name() == "places" else ""
        pinned = Adw.PreferencesGroup(title="Pinned")
        defaults = Adw.PreferencesGroup(title="Everyday places")
        self.places_list.append(pinned); self.places_list.append(defaults)
        if not self.store.places:
            pinned.add(label("Pin a project, document or folder you come back to.", "dim-label", wrap=True))
        entries = [(item, pinned, True) for item in self.store.places]
        entries.extend(({"path": str(path), "name": name}, defaults, False) for name, path in
                       [("Home", HOME), ("Downloads", user_directory("DOWNLOAD")), ("Documents", user_directory("DOCUMENTS")),
                        ("Pictures", user_directory("PICTURES")), ("Screenshots", screenshot_directory())])
        for item, group, removable in entries:
            path = Path(item["path"])
            title = str(item.get("name", path.name))
            if needle not in (title + " " + str(path)).casefold():
                continue
            row = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=GLib.markup_escape_text(str(path)))
            row.set_title_lines(1); row.set_subtitle_lines(1)
            row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic" if path.is_dir() else "text-x-generic-symbolic"))
            row.set_activatable(True); row.connect("activated", lambda _, p=path: self.open_path(p))
            if removable:
                remove = Gtk.Button(icon_name="list-remove-symbolic", tooltip_text="Unpin (keep original)", valign=Gtk.Align.CENTER)
                remove.add_css_class("flat")
                remove.connect("clicked", lambda _, identity=item["id"]: self.unpin(identity))
                row.add_suffix(remove)
            else:
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            group.add(row)

    def colors_page(self):
        scroller, box = self.body()
        box.append(button("Pick from screen", self.pick_color, "color-select-symbolic", "suggested-action"))
        box.append(label("Click a color to copy its hex value. Picking never changes your theme.", "dim-label", wrap=True))
        self.color_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.append(self.color_box)
        return scroller

    def pick_color(self):
        if self.busy:
            return
        if not shutil.which("hyprpicker"):
            self.toast("Install the optional hyprpicker package to pick screen colors."); return
        def done(result, error):
            if error:
                self.toast(error); return
            value = result.stdout.strip()
            if not value:
                self.toast("Picker cancelled"); return
            try:
                self.store.color(value)
                self.refresh_colors(); self.copy_text(value.upper())
            except (ValueError, OSError) as error:
                self.toast(error)
        self.hidden_operation(["hyprpicker", "--format=hex", "--no-fancy"], done)

    def copy_text(self, value):
        Gdk.Display.get_default().get_clipboard().set(value)
        self.toast("Copied " + value)

    def refresh_colors(self):
        clear(self.color_box)
        needle = self.search.get_text().casefold() if self.stack.get_visible_child_name() == "colors" else ""
        for title, values in [("From your wallpaper", [self.colors[key] for key in ("background", "surface", "accent", "text")]),
                              ("Picked by you", self.store.colors)]:
            self.color_box.append(label(title, "heading"))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=1,
                               max_children_per_line=6, row_spacing=10, column_spacing=10, homogeneous=True)
            self.color_box.append(flow)
            for value in dict.fromkeys(values):
                if needle not in value.casefold():
                    continue
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                swatch = Gtk.DrawingArea(height_request=64, width_request=100)
                rgb = tuple(int(value[i:i+2], 16) / 255 for i in (1, 3, 5))
                def draw(widget, context, width, height, color=rgb):
                    context.set_source_rgb(*color); context.paint()
                swatch.set_draw_func(draw)
                content.append(swatch); content.append(Gtk.Label(label=value.upper()))
                choice = Gtk.Button(child=content, tooltip_text="Copy " + value)
                choice.add_css_class("color-chip")
                choice.connect("clicked", lambda _, color=value: self.copy_text(color.upper()))
                flow.insert(choice, -1)
            if not values:
                self.color_box.append(label("Your picked colors will stay here.", "dim-label"))

    def shortcuts_page(self):
        scroller, box = self.body()
        box.append(label("Your configured shortcuts", "title-3"))
        box.append(label("Read from hyprland.lua. Nothing here changes a binding. Ctrl+F searches; Ctrl+R refreshes.", "dim-label", wrap=True))
        self.shortcut_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.shortcut_list.add_css_class("boxed-list")
        box.append(self.shortcut_list)
        return scroller

    def refresh_shortcuts(self):
        clear(self.shortcut_list)
        needle = self.search.get_text().casefold() if self.stack.get_visible_child_name() == "shortcuts" else ""
        for item in shortcuts():
            if needle not in (item["name"] + " " + item["keys"] + " " + item["detail"]).casefold():
                continue
            row = Adw.ActionRow(title=GLib.markup_escape_text(item["name"]), tooltip_text=item["detail"])
            keys = label(item["keys"], "keycap", selectable=True, valign=Gtk.Align.CENTER)
            row.add_suffix(keys)
            self.shortcut_list.append(row)


if __name__ == "__main__":
    raise SystemExit(Shelf().run(sys.argv))
