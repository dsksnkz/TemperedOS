"""Run deployment in a disposable home, with desktop commands blocked."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_isolated_install_preserves_backup_and_monitor_and_launchers(self):
        with tempfile.TemporaryDirectory(prefix="tempered-installer-") as directory:
            home = Path(directory) / "home"
            home.mkdir()
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            calls = Path(directory) / "desktop-calls.txt"
            for name in ("hyprctl", "qs", "quickshell", "gsettings", "sudo", "pacman"):
                tool = bin_dir / name
                tool.write_text('#!/bin/sh\nprintf "%s\\n" "$0" >> "$TEST_CALLS"\nexit 91\n')
                tool.chmod(0o700)
            tool = bin_dir / "waypaper"
            tool.write_text('#!/bin/sh\nprintf "[]\\n"\n'); tool.chmod(0o700)
            old = home / ".config/hypr/hyprland.lua"
            old.parent.mkdir(parents=True)
            old.write_text("-- test previous configuration\n")
            monitor = old.with_name("tempered-monitor.lua")
            monitor.write_text("-- my monitor layout\n")
            config = home / ".config/tempered/settings.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"display_name":"Local Test","rounding":23}')
            env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                   "XDG_DATA_HOME": str(home / ".local/share"), "XDG_STATE_HOME": str(home / ".local/state"),
                   "XDG_CACHE_HOME": str(home / ".cache"), "XDG_RUNTIME_DIR": str(Path(directory) / "runtime"),
                   "HYPRLAND_INSTANCE_SIGNATURE": "", "WAYLAND_DISPLAY": "", "DISPLAY": "",
                   "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
                   "PATH": str(bin_dir) + ":" + os.environ["PATH"], "TEST_CALLS": str(calls)}
            result = subprocess.run(["bash", str(ROOT / "install.sh"), "--yes", "--no-packages"],
                                    env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(calls.exists(), calls.read_text() if calls.exists() else "")
            backups = list((home / ".local/state/tempered-os/backups").glob("*/.config/hypr/hyprland.lua"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "-- test previous configuration\n")
            self.assertEqual(monitor.read_text(), "-- my monitor layout\n")
            self.assertEqual(json.loads(config.read_text())["display_name"], "Local Test")
            for script in (home / ".local/bin").glob("tempered-*"):
                self.assertTrue(os.access(script, os.X_OK), str(script))
            for filename in ("shelf.py", "shelf.css", "shelf_core.py", "capture.py"):
                self.assertTrue((home / ".local/lib/tempered" / filename).is_file())
            palette = json.loads((home / ".config/tempered/picker-colors.json").read_text())
            self.assertTrue(palette["base"].startswith("#"))


if __name__ == "__main__":
    unittest.main()
