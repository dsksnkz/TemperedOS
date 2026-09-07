//@ pragma ShellId tempered-shell
//@ pragma DropExpensiveFonts

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Mpris
import Quickshell.Services.SystemTray
import Quickshell.Wayland

ShellRoot {
    id: shell

    property bool sheetOpen: false
    property string sheet: "controls"
    property var pulse: ({})
    property var palette: ({
        background: "#121923", surface: "#202b39", surfaceRaised: "#2d3948",
        text: "#eef5ff", muted: "#9eabbc", accent: "#7ebeff", accent2: "#9a92ff",
        border: "#b6d4ef", danger: "#ff7482"
    })

    readonly property color bg: palette.background ?? "#121923"
    readonly property color surface: palette.surface ?? "#202b39"
    readonly property color raised: palette.surfaceRaised ?? "#2d3948"
    readonly property color fg: palette.text ?? "#eef5ff"
    readonly property color muted: palette.muted ?? "#9eabbc"
    readonly property color accent: palette.accent ?? "#7ebeff"
    readonly property color accent2: palette.accent2 ?? "#9a92ff"
    readonly property color border: palette.border ?? "#b6d4ef"
    readonly property real motionScale: {
        const prefs = pulse.settings ?? ({})
        if (prefs.reduce_motion || prefs.animations === false)
            return 0
        return Math.max(0.5, Math.min(2, 100 / (prefs.animation_speed ?? 100)))
    }

    function open(name) {
        if (sheetOpen && sheet === name) {
            sheetOpen = false
            return
        }
        sheet = name
        sheetOpen = true
    }

    function run(command) {
        Quickshell.execDetached(["sh", "-lc", command])
    }

    function launch(command) {
        shell.sheetOpen = false
        launchDelay.command = command
        launchDelay.restart()
    }

    Timer {
        id: launchDelay
        property string command: ""
        interval: 120
        onTriggered: shell.run(command)
    }

    IpcHandler {
        target: "tempered"
        function toggle(): void { shell.open("controls") }
        function controls(): void { shell.open("controls") }
        function spaces(): void { shell.open("spaces") }
        function close(): void { shell.sheetOpen = false }
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: window
            required property var modelData
            screen: modelData
            color: "transparent"
            implicitHeight: shell.sheetOpen ? 382 : 66
            exclusiveZone: 66
            focusable: false
            WlrLayershell.namespace: "tempered-island"

            anchors { top: true; left: true; right: true }
            mask: Region { item: clickSurface; radius: 25 }

            Process {
                id: statusFeed
                command: [Quickshell.shellPath("status.py")]
                running: true
                stdout: SplitParser {
                    onRead: data => {
                        try {
                            const next = JSON.parse(data)
                            shell.pulse = next
                            if (next.palette && next.palette.accent)
                                shell.palette = next.palette
                        } catch (error) {
                            console.warn("tempered status:", error)
                        }
                    }
                }
            }

            SystemClock { id: clock; precision: SystemClock.Seconds }

            Item {
                id: clickSurface
                readonly property var prefs: shell.pulse.settings ?? ({})
                width: Math.max(680, Math.min(window.width * ((prefs.island_width ?? 50) / 100), 1160))
                height: shell.sheetOpen ? 370 : 54
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 8

                Rectangle {
                    id: island
                    width: parent.width
                    height: 50
                    radius: 25
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, (clickSurface.prefs.glass_opacity ?? 68) / 100)
                    border.width: 1
                    border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.30)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: 24
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.13) }
                            GradientStop { position: 0.46; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(shell.accent2.r, shell.accent2.g, shell.accent2.b, 0.12) }
                        }
                    }

                    // The rivulet is the island's identity: workspace beads feed into a living center droplet.
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 26
                        anchors.rightMargin: 26
                        height: 1
                        color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.16)
                    }

                    Row {
                        id: workspaces
                        anchors.left: parent.left
                        anchors.leftMargin: 18
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 7

                        Repeater {
                            model: 6
                            Rectangle {
                                required property int index
                                width: shell.pulse.workspace === index + 1 ? 24 : 7
                                height: 7
                                radius: 4
                                color: shell.pulse.workspace === index + 1 ? shell.accent
                                      : Qt.rgba(shell.fg.r, shell.fg.g, shell.fg.b, 0.25)
                                Behavior on width { NumberAnimation { duration: Math.round(240 * shell.motionScale); easing.type: Easing.OutBack } }
                                TapHandler { onTapped: shell.run("hyprctl dispatch workspace " + (index + 1)) }
                            }
                        }
                    }

                    Item {
                        id: nowPond
                        anchors.centerIn: parent
                        width: Math.min(360, parent.width * 0.42)
                        height: parent.height

                        Rectangle {
                            id: droplet
                            anchors.centerIn: parent
                            width: 9 + 2 * Math.sin(Date.now() / 950)
                            height: width
                            radius: width / 2
                            color: shell.accent
                            opacity: 0.88
                            SequentialAnimation on scale {
                                running: shell.motionScale > 0
                                loops: Animation.Infinite
                                NumberAnimation { to: 1.18; duration: Math.round(1300 * shell.motionScale); easing.type: Easing.InOutSine }
                                NumberAnimation { to: 0.92; duration: Math.round(1300 * shell.motionScale); easing.type: Easing.InOutSine }
                            }
                        }

                        Text {
                            anchors.right: droplet.left
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width / 2 - 22
                            horizontalAlignment: Text.AlignRight
                            text: shell.pulse.playing ? (shell.pulse.artist || "Playing")
                                 : Qt.formatDateTime(clock.date, "ddd d MMM")
                            color: shell.muted
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 10
                        }
                        Text {
                            anchors.left: droplet.right
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width / 2 - 22
                            text: shell.pulse.playing ? (shell.pulse.title || "Now playing")
                                 : Qt.formatDateTime(clock.date, clickSurface.prefs.show_seconds ? "HH:mm:ss" : "HH:mm")
                            color: shell.fg
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                        TapHandler { onTapped: shell.open(shell.pulse.playing ? "media" : "controls") }
                    }

                    Row {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4

                        Repeater {
                            model: clickSurface.prefs.island_compact ? [] : SystemTray.items
                            Item {
                                required property var modelData
                                width: 28; height: 32
                                Image { anchors.centerIn: parent; width: 15; height: 15; source: modelData.icon }
                                TapHandler { onTapped: modelData.activate() }
                            }
                        }

                        Rectangle {
                            width: 78; height: 32; radius: 16
                            color: controlsHover.hovered ? Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.18) : "transparent"
                            HoverHandler { id: controlsHover }
                            TapHandler { onTapped: shell.open("controls") }
                            Row {
                                anchors.centerIn: parent; spacing: 7
                                Text { text: shell.pulse.network === "Offline" ? "󰖪" : "󰖩"; color: shell.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 14 }
                                Text { text: (shell.pulse.battery ?? -1) >= 0 ? shell.pulse.battery + "%" : (shell.pulse.cpu ?? 0) + "%"; color: shell.fg; font.family: "Inter"; font.pixelSize: 10; font.weight: Font.DemiBold }
                                Text { text: shell.sheetOpen ? "󰅃" : "󰅀"; color: shell.muted; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 12 }
                            }
                        }
                    }
                }

                Rectangle {
                    id: sheetPanel
                    anchors.top: island.bottom
                    anchors.topMargin: 8
                    width: parent.width
                    height: 304
                    radius: 26
                    visible: opacity > 0.01
                    opacity: shell.sheetOpen ? 1 : 0
                    y: shell.sheetOpen ? 58 : 42
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, Math.min(0.94, ((clickSurface.prefs.glass_opacity ?? 68) + 10) / 100))
                    border.width: 1
                    border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.28)
                    clip: true

                    Behavior on opacity { NumberAnimation { duration: Math.round(180 * shell.motionScale) } }
                    Behavior on y { NumberAnimation { duration: Math.round(260 * shell.motionScale); easing.type: Easing.OutCubic } }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 14

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: shell.sheet === "media" ? "Sound current" : "Your current"
                                color: shell.fg
                                font.family: "Inter"
                                font.pixelSize: 17
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: shell.sheet === "media" ? "one place for playback and output" : "a short path through the machine"
                                color: shell.muted
                                font.family: "Inter"
                                font.pixelSize: 10
                            }
                            Rectangle {
                                width: 58; height: 26; radius: 13
                                color: closeHover.hovered ? Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.18) : Qt.rgba(shell.raised.r, shell.raised.g, shell.raised.b, 0.72)
                                HoverHandler { id: closeHover }
                                TapHandler { onTapped: shell.sheetOpen = false }
                                Text { anchors.centerIn: parent; text: "close"; color: shell.muted; font.family: "JetBrains Mono"; font.pixelSize: 9 }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 16

                            ColumnLayout {
                                Layout.preferredWidth: 236
                                spacing: 10
                                Text { text: "FLOW"; color: shell.accent; font.family: "JetBrains Mono"; font.pixelSize: 9; font.letterSpacing: 1.6 }
                                GlassAction { Layout.fillWidth: true; glyph: "󰖩"; label: shell.pulse.network ?? "Network"; detail: "Connections"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("nm-connection-editor") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰂯"; label: "Bluetooth"; detail: "Devices and handoff"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("blueman-manager") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰂚"; label: "Quiet current"; detail: "Notifications"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("swaync-client --toggle-panel") }
                            }

                            Rectangle { Layout.fillHeight: true; width: 1; color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.14) }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text { text: "PRESSURE"; color: shell.accent2; font.family: "JetBrains Mono"; font.pixelSize: 9; font.letterSpacing: 1.6 }
                                FluidSlider {
                                    Layout.fillWidth: true; glyph: shell.pulse.muted ? "󰖁" : "󰕾"; motionScale: shell.motionScale
                                    value: (shell.pulse.volume ?? 0) / 100; foreground: shell.fg; accent: shell.accent
                                    onMoved: value => shell.run("wpctl set-volume -l 1.25 @DEFAULT_AUDIO_SINK@ " + Math.round(value * 100) + "%")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    GlassAction { Layout.fillWidth: true; glyph: shell.pulse.playing ? "󰏤" : "󰐊"; label: shell.pulse.playing ? "Pause" : "Play"; detail: shell.pulse.title || "No active player"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.run("playerctl play-pause") }
                                    GlassAction { Layout.fillWidth: true; glyph: "󰒓"; label: "Settings"; detail: "Shape the system"; foreground: shell.fg; muted: shell.muted; accent: shell.accent2; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("tempered-settings") }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    GlassAction { Layout.fillWidth: true; glyph: "󰹑"; label: "Capture"; detail: "Select an area"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("tempered-capture") }
                                    GlassAction { Layout.fillWidth: true; glyph: "󰀻"; label: "Orbit Apps"; detail: "Installed software"; foreground: shell.fg; muted: shell.muted; accent: shell.accent2; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("orbitos-apps") }
                                }
                            }

                            Rectangle { Layout.fillHeight: true; width: 1; color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.14) }

                            ColumnLayout {
                                Layout.preferredWidth: 154
                                spacing: 10
                                Text { text: "RELEASE"; color: shell.accent; font.family: "JetBrains Mono"; font.pixelSize: 9; font.letterSpacing: 1.6 }
                                GlassAction { Layout.fillWidth: true; glyph: "󰌾"; label: "Lock"; detail: "Leave it held"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("hyprlock") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰐥"; label: "Power"; detail: "End this session"; foreground: shell.fg; muted: shell.muted; accent: shell.accent2; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("wlogout") }
                                Text { text: "CPU " + (shell.pulse.cpu ?? 0) + "%  ·  RAM " + (shell.pulse.memory ?? 0) + "%"; color: shell.muted; font.family: "JetBrains Mono"; font.pixelSize: 9 }
                            }
                        }
                    }
                }
            }
        }
    }
}
