# Shelf and everyday tools

Open **Tempered Shelf** from the launcher. No keyboard bindings changed.

## Captures

- Capture an area, a selected window, the focused display, or every display.
- Wait 3, 5 or 10 seconds before capture/selection when you need time to prepare.
- Esc cancels area/window selection. Only one capture selection runs at a time.
- Captures are saved in your XDG Pictures folder's `Screenshots` directory and
  copied as PNG. A clipboard failure does not discard the saved file.
- Browse the most recent 120 images, preview, copy, open, pin, or move to Trash.
  Trash always asks first; recover images through your file manager.
- `Super+Shift+S` still captures an area immediately.

Shelf hides itself before capturing. Window capture selects a visible window's
rectangle; it does not reconstruct pixels hidden behind another window.

## Places, colors and shortcuts

- Pin files or folders you choose. Unpinning never deletes the original.
- Pick a screen color, copy its hex value and keep the last 16 distinct colors.
  The current wallpaper palette is shown alongside them. Picking a color does
  not change your wallpaper or theme.
- Search the keyboard guide generated from Tempered's `hyprland.lua`.
  This is a reference, not a keybind editor. Custom Lua-generated bindings outside
  Tempered's standard workspace loop may not be listed.
- `Ctrl+F` focuses search; `Ctrl+R` refreshes.

No recursive indexing, online account, background clipboard collection or cloud
upload is involved. Pins and colors live in `$XDG_STATE_HOME/tempered-os/shelf.json`.
Image thumbnails are private cache files in `$XDG_CACHE_HOME/tempered-os/shelf`.
Shelf runs only when opened. It watches its screenshot directory and palette,
not the rest of your files.

## Launcher additions

Type `>` to find Shelf, pinned places, keyboard shortcuts, screen colors, and
window/display capture actions. Search **Tempered Shelf** in Applications too.

The calculator now supports offline unit conversions:

```text
= 25.4 mm to in
= 13.6 l to cm3
= 1 m2 to cm2
= 20 c to f
= 90 min to h
= 1 gib to mib
```

Enter copies the result. Storage units mean bytes (GB is decimal, GiB is binary).
Currency/live exchange rates are deliberately not supported.

## Reliability follow-through

- Fixed the control wrapper ignoring page names: `tempered-control desk`,
  `spaces`, `media`, `wifi` and `bluetooth` now reach the requested page.
- Desktop health checks executable permissions, including the launcher.
- GTK no longer forces light text onto light accent buttons.
- Launcher icon handling avoids trying to decode an executable as an image.
- Theme writes use unique atomic temporary files. Wallpaper-derived accent
  colors preserve hue and meet 4.5:1 contrast against the dark base.
- The wallpaper picker palette is per-user, not shared through `/tmp`.
- `tempered-theme --no-apply WALLPAPER` generates files without contacting the
  running desktop. The installer uses this when outside a Hyprland session.

## Validation

The regression suite includes a real `install.sh --yes --no-packages` run inside
a disposable home, with desktop/system commands blocked. It verifies backup,
monitor-file preservation, user preference retention and executable entrypoints.
This does not install packages or certify a fresh machine's drivers and services.

```sh
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -input tests/qml -import /usr/lib/qt6/qml
```

Optional GTK smoke tests are `tests/smoke_settings.py` and `tests/smoke_shelf.py`.
Run them in a separate Broadway display or under Xvfb. The latter uses temporary
files and exercises all four pages, pins, colors and preview without touching
hardware or the real clipboard.

## References

[The r/unixporn screenshot-tool discussion](https://www.reddit.com/r/unixporn/comments/1ucx3v4/hyprland_the_screenshot_tool_from_my_rice_is/)
informed the save-and-copy workflow. This is a local GTK implementation, not an
installation or copy of somebody else's desktop. No third-party rice script was run.
