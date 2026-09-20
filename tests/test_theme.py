import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tempered_theme", ROOT / ".local/lib/tempered/theme.py")
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)


def rgb(value):
    return tuple(int(value[index:index+2], 16) for index in (1, 3, 5))


class ThemeTests(unittest.TestCase):
    def test_dark_surface_and_readable_accent_for_extreme_wallpapers(self):
        with tempfile.TemporaryDirectory() as directory:
            wallpaper = Path(directory) / "wallpaper.png"
            for color in ("white", "black", "red", "blue", "lime", "purple", "#808080", "#102938"):
                Image.new("RGB", (16, 16), color).save(wallpaper)
                palette = theme.palette_from(wallpaper)
                background = theme.luminance(rgb(palette["background"]))
                self.assertLess(background, .025, color)
                for role in ("text", "accent", "accent2"):
                    ratio = (theme.luminance(rgb(palette[role])) + .05) / (background + .05)
                    self.assertGreaterEqual(ratio, 4.5, (color, role, ratio))

    def test_atomic_write_no_scratch_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "theme.json"
            sentinel = path.with_suffix(".json.new")
            sentinel.write_text("unrelated")
            theme.atomic_text(path, "new palette")
            self.assertEqual(path.read_text(), "new palette")
            self.assertEqual(sentinel.read_text(), "unrelated")
            self.assertEqual(list(Path(directory).glob(".tempered-*")), [])


if __name__ == "__main__":
    unittest.main()
