"""Hardware-free regression tests for the desktop's small state machines."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


desk = module("desk", ".config/quickshell/tempered/desk.py")
history = module("history", ".config/quickshell/tempered-launcher/history.py")
brightness = module("brightness", ".local/lib/tempered/brightness.py")


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "desk.json"
        self.desk = desk.Desk(self.path)

    def test_note_survives_restart_and_is_private(self):
        self.desk.command({"action": "note", "text": "A thought — 你好\nSecond line"}, 100)
        self.assertEqual(desk.Desk(self.path).data["note"], self.desk.data["note"])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_pause_resume_deadline_and_complete_once(self):
        self.desk.command({"action": "start", "minutes": 1}, 100)
        self.assertEqual(self.desk.remaining(115), 45)
        self.desk.command({"action": "pause"}, 115)
        restored = desk.Desk(self.path)
        self.assertEqual(restored.remaining(1000), 45)
        restored.command({"action": "resume"}, 1000)
        self.assertIsNone(restored.tick(1044))
        self.assertEqual(restored.tick(1045), "Focus complete")
        self.assertIsNone(restored.tick(1046))
        self.assertEqual(restored.snapshot(1046)["today"], 1)
        self.assertIsNone(desk.Desk(self.path).tick(1100))

    def test_running_deadline_survives_restart(self):
        self.desk.command({"action": "start", "minutes": 25}, 100)
        self.assertEqual(desk.Desk(self.path).remaining(200), 1400)

    def test_break_does_not_count_as_focus(self):
        self.desk.command({"action": "start", "minutes": 1, "kind": "break"}, 100)
        self.assertEqual(self.desk.tick(160), "Break complete")
        self.assertEqual(self.desk.snapshot(160)["today"], 0)

    def test_corrupt_original_preserved(self):
        self.path.write_text("my damaged but recoverable note")
        recovered = desk.Desk(self.path)
        recovered.command({"action": "note", "text": "New note"}, 100)
        self.assertEqual(self.path.read_text(), "my damaged but recoverable note")
        self.assertEqual(recovered.path.name, "desk-recovered.json")
        self.assertEqual(desk.Desk(self.path).data["note"], "New note")

    def test_reject_invalid_commands(self):
        for message in ({"action": "start", "minutes": -1}, {"action": "start", "minutes": float("nan")},
                        {"action": "note", "text": "x" * 16001}, {"action": "exec", "text": "false"}):
            with self.assertRaises(ValueError):
                self.desk.command(message, 100)

    def test_batched_stdin_commands_are_not_lost(self):
        worker = subprocess.Popen(["python3", str(ROOT / ".config/quickshell/tempered/desk.py")],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env={**os.environ, "XDG_STATE_HOME": self.directory.name})
        commands = b'{"action":"note","text":"first"}\n{"action":"note","text":"last"}\n'
        out, err = worker.communicate(commands, timeout=5)
        self.assertEqual(worker.returncode, 0, err)
        saved = json.loads((Path(self.directory.name) / "tempered-os/desk.json").read_text())
        self.assertEqual(saved["note"], "last")


class HistoryTests(unittest.TestCase):
    def test_pin_toggle_and_recent_deduplication(self):
        data = history.update({}, "pin", "kitty")
        data = history.update(data, "record", "kitty")
        data = history.update(data, "record", "kitty")
        self.assertEqual(data, {"pins": ["kitty"], "recent": ["kitty"]})
        self.assertEqual(history.update(data, "pin", "kitty")["pins"], [])

    def test_malformed_saved_fields_are_safe(self):
        self.assertEqual(history.update({"pins": 3, "recent": None}, "get", ""), {"pins": [], "recent": []})


class BrightnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        names = {"CACHE_DIR": base, "VALUE_FILE": base / "value", "BUS_FILE": base / "bus", "LOCK_FILE": base / "worker.lock",
                 "REQUEST_FILE": base / "request.json", "REQUEST_LOCK": base / "request.lock", "ERROR_FILE": base / "error"}
        for key, value in names.items():
            patcher = patch.object(brightness, key, value); patcher.start(); self.addCleanup(patcher.stop)
        brightness.VALUE_FILE.write_text("50")
        patcher = patch.object(brightness, "find_ddc", return_value=("7", 50)); patcher.start(); self.addCleanup(patcher.stop)

    def test_fast_drags_coalesce_to_latest_not_full_queue(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        def driver(bus, value):
            writes.append(value)
            if len(writes) == 1:
                entered.set(); self.assertTrue(release.wait(3))
            return True
        with patch.object(brightness, "set_value", side_effect=driver), contextlib.redirect_stdout(io.StringIO()):
            worker = threading.Thread(target=brightness.submit, args=("set", 20))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                for target in range(21, 91):
                    brightness.submit("set", target)
            finally:
                release.set(); worker.join(3)
            self.assertFalse(worker.is_alive())
        self.assertEqual(writes, [20, 90])
        self.assertEqual(brightness.cached_value(), 90)
        self.assertFalse(brightness.request()["pending"])

    def test_repeated_keyboard_steps_accumulate(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        def driver(bus, value):
            writes.append(value)
            if len(writes) == 1:
                entered.set(); release.wait(3)
            return True
        with patch.object(brightness, "set_value", side_effect=driver), contextlib.redirect_stdout(io.StringIO()):
            worker = threading.Thread(target=brightness.submit, args=("change", 5))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                for _ in range(4):
                    brightness.submit("change", 5)
            finally:
                release.set(); worker.join(3)
        self.assertEqual(writes, [55, 75])

    def test_failure_keeps_actual_brightness_and_reports_error(self):
        with patch.object(brightness, "set_value", return_value=False), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(brightness.submit("set", 80), 1)
        self.assertEqual(brightness.cached_value(), 50)
        self.assertTrue(brightness.ERROR_FILE.read_text())
        self.assertFalse(brightness.request()["pending"])

    def test_clamps_to_safe_range(self):
        with patch.object(brightness, "set_value", return_value=True) as driver, contextlib.redirect_stdout(io.StringIO()):
            brightness.submit("set", -50)
            self.assertEqual(driver.call_args.args[1], 5)
            brightness.submit("set", 180)
            self.assertEqual(driver.call_args.args[1], 100)


if __name__ == "__main__":
    unittest.main()
