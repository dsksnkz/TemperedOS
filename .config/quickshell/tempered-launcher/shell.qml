//@ pragma ShellId tempered-launcher
//@ pragma AppId io.github.dsksnkz.TemperedOS.Launcher

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets
import "Calculator.js" as Calculator

FloatingWindow {
    id: root
    visible: true
    title: "Tempered Launcher"
    color: "transparent"
    implicitWidth: 780
    implicitHeight: 520

    property int mode: Quickshell.env("TEMPERED_LAUNCHER_MODE") === "windows" ? 1 : Quickshell.env("TEMPERED_LAUNCHER_MODE") === "actions" ? 2 : 0
    property var history: ({pins: [], recent: []})
    readonly property bool calculating: search.text.trim().startsWith("=")
    readonly property var calculation: Calculator.calculate(search.text)
    property string copied: ""
    property var resolvedIcons: ({})

    function applicationIcon(name) {
        if (!name) return Quickshell.shellPath("application.svg")
        if (resolvedIcons[name]) return resolvedIcons[name]
        // Some .desktop files incorrectly name an executable as their icon.
        // Wait for the MIME-checked lookup for extensionless file icons.
        if (name.startsWith("/") || name.startsWith("file://")) {
            if (/\.(png|svg|svgz|jpg|jpeg|webp|xpm|ico)$/i.test(name)) return name.startsWith("/") ? "file://" + name : name
            return Quickshell.shellPath("application.svg")
        }
        return resolvedIcons[name] || Quickshell.iconPath(name, true) || Quickshell.shellPath("application.svg")
    }

    Process {
        running: true
        command: ["python3", Quickshell.shellPath("icons.py")]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.resolvedIcons = JSON.parse(this.text) }
                catch (error) { console.warn("Icon lookup unavailable:", error) }
            }
        }
    }
    property var palette: ({
        background: "#121923", surface: "#202b39", surfaceRaised: "#2d3948",
        text: "#eef5ff", muted: "#9eabbc", accent: "#7ebeff",
        accent2: "#9a92ff", border: "#b6d4ef"
    })
    readonly property color bg: palette.background ?? "#121923"
    readonly property color surface: palette.surface ?? "#202b39"
    readonly property color raised: palette.surfaceRaised ?? "#2d3948"
    readonly property color fg: palette.text ?? "#eef5ff"
    readonly property color muted: palette.muted ?? "#9eabbc"
    readonly property color accent: palette.accent ?? "#7ebeff"
    readonly property color accent2: palette.accent2 ?? "#9a92ff"
    readonly property color border: palette.border ?? "#b6d4ef"
    readonly property string needle: search.text.trim().replace(/^>\s*/, "").toLowerCase()
    function score(entry) {
        const name = entry.name.toLowerCase(), extra = ((entry.comment || "") + " " + (entry.genericName || "")).toLowerCase()
        if (!needle) return (history.pins.includes(entry.id) ? 200 : 0) + Math.max(0, 60 - history.recent.indexOf(entry.id) * 2) * (history.recent.includes(entry.id) ? 1 : 0)
        if (name.startsWith(needle)) return 100
        if (name.includes(needle)) return 80
        if (extra.includes(needle)) return 40
        let position = -1
        for (const char of needle) { position = name.indexOf(char, position + 1); if (position < 0) return -1 }
        return 20 - position / 100
    }
    onNeedleChanged: { resultList.currentIndex = 0; if (search.text.trim().startsWith(">")) mode = 2 }
    readonly property var apps: DesktopEntries.applications.values
        .filter(entry => !entry.noDisplay && score(entry) >= 0)
        .sort((left, right) => score(right) - score(left) || left.name.localeCompare(right.name))
    readonly property var windows: Hyprland.toplevels.values
        .filter(item => item.title && (needle.length === 0 || item.title.toLowerCase().includes(needle)))
    readonly property var actions: [
        {name: "Open Shelf", comment: "Captures, pinned places, colors and keyboard shortcuts", icon: "folder-pictures-symbolic", command: "~/.local/bin/tempered-shelf"},
        {name: "Pinned places", comment: "Your project folders and important files", icon: "folder-symbolic", command: "~/.local/bin/tempered-shelf --places"},
        {name: "Keyboard shortcuts", comment: "Search your configured keybinds", icon: "input-keyboard-symbolic", command: "~/.local/bin/tempered-shelf --shortcuts"},
        {name: "Screen colors", comment: "Pick, save and copy colors without changing your theme", icon: "color-select-symbolic", command: "~/.local/bin/tempered-shelf --colors"},
        {name: "Capture a window", comment: "Select a window; save and copy a screenshot", icon: "camera-photo-symbolic", command: "~/.local/bin/tempered-capture window"},
        {name: "Capture this display", comment: "Screenshot the focused monitor", icon: "video-display-symbolic", command: "~/.local/bin/tempered-capture screen"},
        {name: "Your desk", comment: "Calendar, focus timer and private notes", icon: "user-home-symbolic", command: "~/.local/bin/tempered-control desk"},
        {name: "Control centre", comment: "Sound, brightness and connected devices", icon: "preferences-system-symbolic", command: "~/.local/bin/tempered-control controls"},
        {name: "Workspace atlas", comment: "Find your open work", icon: "view-grid-symbolic", command: "~/.local/bin/tempered-control spaces"},
        {name: "Now playing", comment: "Music, media and playback controls", icon: "audio-x-generic-symbolic", command: "~/.local/bin/tempered-control media"},
        {name: "Personal settings", comment: "Your profile and desktop preferences", icon: "emblem-system-symbolic", command: "~/.local/bin/tempered-settings"},
        {name: "Change wallpaper", comment: "New scenery, new colors", icon: "preferences-desktop-wallpaper-symbolic", command: "~/.local/bin/tempered-wallpaper-picker"},
        {name: "Capture an area", comment: "Save a screenshot and copy it", icon: "camera-photo-symbolic", command: "~/.local/bin/tempered-capture"},
        {name: "Clipboard history", comment: "Find something you copied", icon: "edit-paste-symbolic", command: "kitty --class clipse -e clipse"},
        {name: "Notifications", comment: "Catch up with your desktop", icon: "preferences-system-notifications-symbolic", command: "swaync-client --toggle-panel"},
        {name: "Power menu", comment: "Choose a session action", icon: "system-shutdown-symbolic", command: "~/.local/bin/tempered-power"},
        {name: "Desktop health", comment: "Check your setup without changing it", icon: "emblem-ok-symbolic", command: "kitty --title 'Desktop health' --hold -e ~/.local/bin/tempered-doctor"}
    ].filter(action => !needle || (action.name + " " + action.comment).toLowerCase().includes(needle))
    readonly property var results: mode === 0 ? apps : mode === 1 ? windows : actions

    function pinCurrent() {
        if (mode !== 0 || !results.length) return
        const id = results[resultList.currentIndex].id
        const pins = history.pins.includes(id) ? history.pins.filter(p => p !== id) : history.pins.concat([id])
        history = {pins: pins, recent: history.recent}
        Quickshell.execDetached(["python3", Quickshell.shellPath("history.py"), "pin", id])
    }
    Process {
        running: true; command: ["python3", Quickshell.shellPath("history.py")]
        stdout: StdioCollector { onStreamFinished: { try { root.history = JSON.parse(this.text) } catch (error) {} } }
    }
    Process {
        id: copyResult
        command: ["wl-copy"]
        stdinEnabled: true
        onStarted: { write(root.calculation.value); stdinEnabled = false }
        onExited: (code, status) => { root.copied = code === 0 ? "Copied" : "Could not copy" }
    }

    function activateCurrent() {
        if (calculating) { if (calculation.value) { copyResult.stdinEnabled = true; copyResult.running = true } return }
        if (results.length === 0)
            return
        const target = results[Math.max(0, Math.min(results.length - 1, resultList.currentIndex))]
        if (mode === 0) {
            Quickshell.execDetached(["python3", Quickshell.shellPath("history.py"), "record", target.id])
            target.execute()
        } else if (mode === 1) {
            if (target.wayland) target.wayland.activate()
            else Hyprland.dispatch(Hyprland.usingLua ? "hl.dsp.focus({window='address:0x" + target.address.replace(/^0x/, "") + "'})" : "focuswindow address:0x" + target.address.replace(/^0x/, ""))
        } else {
            // Delay panel actions until the launcher releases keyboard focus.
            Quickshell.execDetached(["sh", "-lc", "sleep 0.15; " + target.command])
        }
        Qt.quit()
    }

    onVisibleChanged: if (!visible) Qt.quit()

    IpcHandler {
        target: "launcher"
        function query(text: string): void { search.text = text; search.forceActiveFocus() }
        function setMode(value: int): void { root.mode = Math.max(0, Math.min(2, value)); resultList.currentIndex = 0 }
        function inspect(): string { return JSON.stringify({mode: root.mode, count: root.results.length, calculator: root.calculation, names: root.results.slice(0, 6).map(r => r.name || r.title)}) }
        function close(): void { Qt.quit() }
    }

    Process {
        running: true
        command: ["sh", "-lc", "cat \"$HOME/.config/tempered/palette.json\" 2>/dev/null || true"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.palette = JSON.parse(this.text) }
                catch (error) { }
            }
        }
    }

    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }
    Shortcut { sequence: "Tab"; onActivated: { root.mode = (root.mode + 1) % 3; resultList.currentIndex = 0 } }
    Shortcut { sequence: "Alt+P"; onActivated: root.pinCurrent() }

    Rectangle {
        anchors.fill: parent
        radius: 20
        color: Qt.rgba(root.surface.r, root.surface.g, root.surface.b, 0.93)
        border.width: 1
        border.color: Qt.rgba(root.border.r, root.border.g, root.border.b, 0.30)

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 19
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.13) }
                GradientStop { position: 0.55; color: "transparent" }
                GradientStop { position: 1; color: Qt.rgba(root.accent2.r, root.accent2.g, root.accent2.b, 0.10) }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                height: 54
                radius: 18
                color: Qt.rgba(root.raised.r, root.raised.g, root.raised.b, 0.80)
                border.width: search.activeFocus ? 1 : 0
                border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.66)

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    spacing: 12
                    Text { text: "󰍉"; color: root.accent; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 17 }
                    TextInput {
                        id: search
                        Layout.fillWidth: true
                        focus: true
                        color: root.fg
                        selectionColor: root.accent
                        selectedTextColor: root.bg
                        font.family: "Inter"
                        font.pixelSize: 15
                        clip: true
                        Keys.onDownPressed: resultList.currentIndex = Math.min(root.results.length - 1, resultList.currentIndex + 1)
                        Keys.onUpPressed: resultList.currentIndex = Math.max(0, resultList.currentIndex - 1)
                        Keys.onReturnPressed: root.activateCurrent()
                        Keys.onEnterPressed: root.activateCurrent()
                        Keys.onTabPressed: { root.mode = (root.mode + 1) % 3; resultList.currentIndex = 0 }
                        onTextChanged: root.copied = ""
                        Text { visible: search.text.length === 0; text: root.mode === 0 ? "Apps, = calculations, > actions" : root.mode === 1 ? "Search open windows" : "Find a desktop action"; color: root.muted; font: search.font }
                    }
                    Text { text: "esc"; color: root.muted; font.family: "JetBrains Mono"; font.pixelSize: 10 }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: ["Applications", "Windows", "Actions"]
                    Rectangle {
                        required property int index
                        required property string modelData
                        Layout.preferredWidth: 116
                        height: 34
                        radius: 13
                        color: root.mode === index ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22) : modeHover.hovered ? Qt.rgba(root.raised.r, root.raised.g, root.raised.b, 0.72) : "transparent"
                        Text { anchors.centerIn: parent; text: modelData; color: root.mode === index ? root.fg : root.muted; font.family: "Inter"; font.pixelSize: 11; font.weight: root.mode === index ? Font.DemiBold : Font.Normal }
                        HoverHandler { id: modeHover }
                        TapHandler { onTapped: { root.mode = index; resultList.currentIndex = 0; search.forceActiveFocus() } }
                    }
                }
                Item { Layout.fillWidth: true }
                Text { text: root.calculating ? "On-device" : root.results.length + (root.results.length === 1 ? " result" : " results"); color: root.muted; font.family: "Inter"; font.pixelSize: 10 }
            }

            ListView {
                id: resultList
                visible: !root.calculating
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: root.results
                spacing: 5
                clip: true
                currentIndex: 0
                boundsBehavior: Flickable.StopAtBounds
                highlightMoveDuration: 95
                highlightResizeDuration: 95
                highlight: Rectangle { radius: 17; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22); border.width: 1; border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.24) }

                delegate: Item {
                    required property var modelData
                    required property int index
                    width: resultList.width
                    height: 58

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 13
                        Rectangle {
                            width: 38; height: 38; radius: 12
                            color: Qt.rgba(root.raised.r, root.raised.g, root.raised.b, 0.78)
                            Image {
                                visible: root.mode !== 1
                                anchors.centerIn: parent
                                width: 25; height: 25
                                fillMode: Image.PreserveAspectFit
                                source: root.mode !== 1 ? root.applicationIcon(modelData.icon) : ""
                                onStatusChanged: if (status === Image.Error) source = Quickshell.shellPath("application.svg")
                            }
                            Text { visible: root.mode === 1; anchors.centerIn: parent; text: "󰖲"; color: root.accent; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 15 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { text: root.mode !== 1 ? modelData.name : modelData.title; color: root.fg; font.family: "Inter"; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: root.mode !== 1 ? (modelData.comment || modelData.genericName || "Application") : "Workspace " + (modelData.workspace?.id ?? "") + " · Open window"; color: root.muted; font.family: "Inter"; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
                        Text { visible: root.mode === 0 && root.history.pins.includes(modelData.id); text: "★"; color: root.accent; font.pixelSize: 14 }
                        Text { text: index === resultList.currentIndex ? "↵" : ""; color: root.accent; font.family: "Inter"; font.pixelSize: 14 }
                    }
                    HoverHandler { onHoveredChanged: if (hovered) resultList.currentIndex = index }
                    TapHandler { onTapped: { resultList.currentIndex = index; root.activateCurrent() } }
                }

                Text {
                    visible: root.results.length === 0
                    anchors.centerIn: parent
                    text: "No matches"
                    color: root.muted
                    font.family: "Inter"
                    font.pixelSize: 13
                }
            }

            Rectangle {
                visible: root.calculating
                Layout.fillWidth: true; Layout.fillHeight: true
                radius: 20; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, .08)
                Column {
                    anchors.centerIn: parent; width: parent.width - 48; spacing: 16
                    Text { text: root.calculation.value || root.calculation.error; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: root.fg; font.family: "Inter"; font.pixelSize: root.calculation.value ? 40 : 15 }
                    Text { text: root.copied || (root.calculation.value ? "Enter to copy the result" : "Try = 25.4 mm to in · Calculations stay on your device"); width: parent.width; horizontalAlignment: Text.AlignHCenter; color: root.muted; font.family: "Inter"; font.pixelSize: 11 }
                }
                TapHandler { onTapped: root.activateCurrent() }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.calculating ? "↵ copy    esc close" : "↑↓ move    ↵ open    tab switch    alt+p pin"
                color: root.muted
                font.family: "JetBrains Mono"
                font.pixelSize: 9
            }
        }
    }
}
