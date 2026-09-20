"""GTK construction/interaction test with isolated data and no hardware actions.

Run using a separate Broadway display or xvfb-run. No screenshot is taken.
"""
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/lib/tempered"))

with tempfile.TemporaryDirectory(prefix="tempered-shelf-ui-") as directory:
    # Set these before importing GTK to avoid a portal connecting to the live bus.
    os.environ["XDG_STATE_HOME"] = directory + "/state"
    os.environ["XDG_CACHE_HOME"] = directory + "/cache"
    os.environ["XDG_CONFIG_HOME"] = directory + "/config"
    import shelf
    import shelf_core
    from PIL import Image
    from gi.repository import GLib
    folder = Path(directory) / "captures"
    folder.mkdir()
    Image.new("RGB", (640, 360), "#346b81").save(folder / "test-capture.png")
    shelf.captures = lambda: [folder / "test-capture.png"]
    shelf.screenshot_directory = lambda: folder
    shelf.shortcuts = lambda: shelf_core.shortcuts(ROOT / ".config/hypr/hyprland.lua")
    app = shelf.Shelf()
    result_code = 1  # A display/startup failure must not look like a passing test.

    def exercise():
        global result_code
        try:
            for name in ("captures", "places", "colors", "shortcuts"):
                app.stack.set_visible_child_name(name)
                app.search.set_text("test")
                app.search_changed()
                app.search.set_text("")
                app.search_changed()
                assert app.stack.get_visible_child_name() == name
                print("PASS Shelf page:", name, flush=True)
            app.pin_path(folder)
            assert len(app.store.places) == 1
            app.unpin(app.store.places[0]["id"])
            assert folder.is_dir()
            app.store.color("#12ABCD")
            app.refresh_colors()
            app.preview(folder / "test-capture.png")
            print("PASS Pin/unpin, colors, preview", flush=True)
            result_code = 0
        except Exception:
            result_code = 1
            traceback.print_exc()
        GLib.timeout_add(1000, lambda: app.quit() or False)
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(1000, exercise)
    app.run(["shelf-smoke"])
    raise SystemExit(result_code)
