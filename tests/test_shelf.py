"""Shelf and capture regressions. No compositor, clipboard or private files touched."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/lib/tempered"))
import shelf_core as core
import capture


class ShelfTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_pin_deduplicate_and_unpin_preserves_original(self):
        path = self.root / "folder with spaces"
        path.mkdir()
        store = core.ShelfStore(self.root / "shelf.json")
        self.assertTrue(store.pin(path))
        self.assertFalse(store.pin(path))
        restored = core.ShelfStore(store.path)
        self.assertEqual(restored.places[0]["path"], str(path))
        restored.unpin(restored.places[0]["id"])
        self.assertTrue(path.is_dir())
        self.assertEqual(core.ShelfStore(store.path).places, [])
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)

    def test_recovery_keeps_original_and_resumes_recovered(self):
        path = self.root / "shelf.json"
        path.write_text("broken original")
        store = core.ShelfStore(path)
        store.color("#123abc")
        self.assertEqual(path.read_text(), "broken original")
        self.assertEqual(core.ShelfStore(path).colors, ["#123ABC"])

    def test_colors_validated_deduplicated_bounded(self):
        store = core.ShelfStore(self.root / "shelf.json")
        for value in range(20):
            store.color(f"#{value:06x}")
        store.color("#000013")
        self.assertEqual(len(core.ShelfStore(store.path).colors), 16)
        for bad in ("red", "#gg1122", "#123456; shell", "#123"):
            with self.assertRaises(ValueError):
                store.color(bad)

    def test_wrong_data_types_do_not_crash(self):
        path = self.root / "shelf.json"
        path.write_text(json.dumps({"places": "broken", "colors": 34}))
        store = core.ShelfStore(path)
        self.assertEqual(store.places, [])
        self.assertEqual(store.colors, [])

    def test_xdg_paths_never_evaluate_shell(self):
        config = self.root / "user-dirs.dirs"
        config.write_text('XDG_PICTURES_DIR="$HOME/Art folder"\n')
        with patch.object(core, "CONFIG", self.root), patch.object(core, "HOME", self.root):
            self.assertEqual(core.screenshot_directory(), self.root / "Art folder/Screenshots")
            config.write_text('XDG_PICTURES_DIR="$(touch /tmp/not-run)"\n')
            self.assertEqual(core.user_directory("PICTURES"), self.root / "Pictures")
            self.assertEqual(core.user_directory("DOWNLOAD"), self.root / "Downloads")

    def test_gallery_ignores_symlinks_and_private_dot_capture(self):
        older = self.root / "old.png"; older.write_bytes(b"png")
        newer = self.root / "new.png"; newer.write_bytes(b"png")
        os.utime(older, (100, 100)); os.utime(newer, (200, 200))
        (self.root / "link.png").symlink_to(newer)
        (self.root / ".capture-working.png").write_bytes(b"incomplete")
        (self.root / "directory.png").mkdir()
        self.assertEqual(core.captures(self.root), [newer, older])

    def test_names_are_unique(self):
        self.assertNotEqual(core.capture_name(self.root), core.capture_name(self.root))

    def test_shortcuts_come_from_config(self):
        entries = core.shortcuts(ROOT / ".config/hypr/hyprland.lua")
        self.assertGreater(len(entries), 35)
        self.assertTrue(any(item["name"] == "Open terminal" and "W" in item["keys"] for item in entries))
        self.assertTrue(any(item["name"] == "Move window to e+1" and "Shift" in item["keys"] for item in entries))


class CaptureTests(unittest.TestCase):
    def test_cancel_makes_no_file_and_does_not_copy(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "selection", side_effect=capture.Cancelled), patch.object(capture, "execute") as execute:
            with self.assertRaises(capture.Cancelled):
                capture.capture("area", 0, True, Path(directory))
            execute.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_failed_capture_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "selection", return_value=[]), patch.object(capture, "execute", side_effect=RuntimeError("no compositor")):
            with self.assertRaises(RuntimeError):
                capture.capture("screen", 0, True, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_saved_file_is_private_and_clipboard_failure_nonfatal(self):
        def execute(args, **kwargs):
            if args[0] == "grim":
                Path(args[-1]).write_bytes(b"fakepng")
                return b""
            raise RuntimeError("clipboard unavailable")
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "selection", return_value=[]), patch.object(capture, "execute", side_effect=execute):
            target, warning = capture.capture("screen", 0, True, Path(directory))
            self.assertEqual(target.read_bytes(), b"fakepng")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertIn("clipboard", warning)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_window_selection_ignores_hidden_workspaces(self):
        monitors = [{"activeWorkspace": {"id": 2}, "specialWorkspace": {"id": 0}}]
        clients = [{"mapped": True, "hidden": False, "workspace": {"id": workspace}, "at": [10, 20], "size": [300, 200]} for workspace in [2, 3]]
        with patch.object(capture, "execute", side_effect=[json.dumps(monitors).encode(), json.dumps(clients).encode()]), patch.object(capture.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"10,20 300x200\n", b"")) as run:
            self.assertEqual(capture.selection("window"), ["-g", "10,20 300x200"])
            self.assertEqual(run.call_args.kwargs["input"], b"10,20 300x200\n")


class EntrypointTests(unittest.TestCase):
    def test_all_entrypoints_are_executable(self):
        for path in (ROOT / ".local/bin").glob("tempered-*"):
            self.assertTrue(os.access(path, os.X_OK), path.name)

    def test_control_wrapper_passes_page_and_rejects_arbitrary_input(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "quickshell"
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            binary.chmod(0o700)
            env = {**os.environ, "PATH": directory + ":" + os.environ["PATH"]}
            wrapper = str(ROOT / ".local/bin/tempered-control")
            for page in ("desk", "media", "spaces", "wifi", "diagnostics"):
                result = subprocess.run([wrapper, page], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.splitlines()[-1], page)
            self.assertEqual(subprocess.run([wrapper, "not-a-page"], env=env, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
