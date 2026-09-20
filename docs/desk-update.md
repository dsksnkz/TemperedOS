# The personal desk pass

Tempered keeps the wallpaper, existing shortcuts and quiet half-width island.
The new surfaces give that island something useful to do.

- **Desk**: a month calendar, a private auto-saving scratchpad, and 25/50-minute
  focus sessions with pause/resume and a five-minute break. The timer survives
  shell restarts. It notifies at completion while the shell is running; this is
  not a wake-from-suspend alarm.
- **Controls**: live PipeWire volume, mute, microphone mute and output selection;
  brightness with a large drag target and one commit on release.
- **Sound**: native MPRIS metadata, artwork, player selection, seek and playback.
  The island's optional CAVA bars measure audio and stop when playback stops.
- **Spaces**: a workspace overview with direct window selection.
- **Launcher**: three modes, fuzzy app matching, pinned/recent apps, and safe
  arithmetic. Type `>` for actions or `=` for calculations. `Alt+P` pins the
  selected app; `Enter` copies a calculation. No arbitrary command execution.
- **Settings**: a local display name and profile picture, pages loaded on demand,
  and toggles for island feedback and audio visualization.
- **Desktop health**: `tempered-doctor` checks prerequisites and the live shell
  without changing settings or restarting anything.

## Local data

Notes, focus state and launcher history live in
`$XDG_STATE_HOME/tempered-os` (normally `~/.local/state/tempered-os`). They are
not included in the dotfiles repository. Notes are saved with user-only file
permissions. The calculator never uses `eval`, a shell or an online service.
Profiles change the desktop display name, not the Linux account name.

## Reliability changes

One status feed serves all monitors. Audio, media and workspaces use native
event-driven services instead of repeated `wpctl`, `playerctl` and `hyprctl`
polling. Brightness uses a latest-wins mailbox: rapid drags do not queue dozens
of old monitor writes. Keyboard brightness steps still accumulate.

No graphics driver, compositor replacement, game configuration, login-manager,
lock-screen authentication or existing keyboard binding change is required.

## References and design decisions

- [k4 island/dock discussion on r/unixporn](https://www.reddit.com/r/unixporn/comments/1vwb8jk/hyprland_my_island_bar_can_now_become_a_dock/):
  reveal useful controls on demand instead of filling the desktop with widgets.
- [Noctalia's control centre](https://docs.noctalia.dev/noctalia/control-center/):
  consistent grouping and direct controls.
- [End-4 Material 3 showcase on YouTube](https://www.youtube.com/watch?v=OnxU419vnts):
  found as a wallpaper-adaptive reference; the video stream could not be fetched,
  so no frame-by-frame review is claimed.

These are references, not installed replacement desktops. The new implementation
is native to Tempered's existing Quickshell and GTK code.

## Tests

```sh
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -input tests/qml -import /usr/lib/qt6/qml
# Optional: every GTK page, with hardware actions stubbed
GDK_BACKEND=x11 xvfb-run -a python tests/smoke_settings.py
```

Real Bluetooth pairing, suspend/resume and login should not be automated on an
unattended laptop with unsaved work. Read-only checks are not evidence that those
hardware paths have been tested end to end.
