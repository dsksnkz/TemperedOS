#!/usr/bin/env python3
"""Opt-in GTK construction test. Run under xvfb-run, not on your live desktop.

Hardware reads and all writes/launches are stubbed. This verifies every Settings
page can be constructed and selected without manipulating the host session.
"""
import importlib.util
from pathlib import Path
import tempfile
import traceback

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tempered_settings", root / ".local/lib/tempered/settings.py")
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)

with tempfile.TemporaryDirectory(prefix="tempered-settings-test-") as directory:
    settings.SETTINGS_FILE = Path(directory) / "settings.json"
    settings.STATE = Path(directory)
    settings.output = lambda args, fallback="": fallback
    settings.run = lambda *args, **kwargs: None
    settings.detached = lambda *args, **kwargs: None
    settings.sinks = lambda: [("test.speaker", "Built-in speakers"), ("test.bluetooth", "Bluetooth headphones")]
    settings.sources = lambda: [("test.mic", "Built-in microphone")]
    app = settings.TemperedSettings()
    result_code = 1

    def exercise():
        global result_code
        try:
            for name in app.page_factories:
                app.select_page(name)
                assert app.stack.get_visible_child_name() == name, name
                print("PASS Settings page:", name, flush=True)
            app.set_display_name("Local test")
            assert settings.load()["display_name"] == "Local test"
            result_code = 0
        except Exception:
            traceback.print_exc()
        app.quit()
        return settings.GLib.SOURCE_REMOVE

    settings.GLib.timeout_add(500, exercise)
    app.run(["tempered-settings-smoke"])
    raise SystemExit(result_code)
