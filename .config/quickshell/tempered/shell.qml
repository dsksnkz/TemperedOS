//@ pragma ShellId tempered-shell
//@ pragma DropExpensiveFonts

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Networking
import Quickshell.Bluetooth
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
    readonly property int activeWorkspace: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : (pulse.workspace ?? 1)
    readonly property var wifiDevice: {
        const devices = Networking.devices.values
        for (let index = 0; index < devices.length; index++)
            if (devices[index].type === DeviceType.Wifi)
                return devices[index]
        return null
    }
    readonly property var bluetoothAdapter: Bluetooth.defaultAdapter
    property var passwordNetwork: null
    property real visualPhase: 0
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

    function activateWorkspace(workspaceId) {
        const spaces = Hyprland.workspaces.values
        for (let index = 0; index < spaces.length; index++) {
            if (spaces[index].id === workspaceId) {
                spaces[index].activate()
                return
            }
        }
    }

    Process {
        id: paletteReload
        command: ["sh", "-lc", "cat \"$HOME/.config/tempered/palette.json\""]
        stdout: StdioCollector {
            onStreamFinished: {
                try { shell.palette = JSON.parse(this.text) }
                catch (error) { console.warn("tempered palette:", error) }
            }
        }
    }

    Timer {
        id: launchDelay
        property string command: ""
        interval: 120
        onTriggered: shell.run(command)
    }

    Timer {
        interval: 82
        repeat: true
        running: shell.pulse.playing === true
        onTriggered: shell.visualPhase += 0.34
    }

    IpcHandler {
        target: "tempered"
        function toggle(): void { shell.open("controls") }
        function controls(): void { shell.open("controls") }
        function spaces(): void { shell.open("spaces") }
        function wifi(): void { shell.open("wifi") }
        function bluetooth(): void { shell.open("bluetooth") }
        function recolor(): void { paletteReload.running = true }
        function close(): void { shell.sheetOpen = false }
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: window
            required property var modelData
            screen: modelData
            color: "transparent"
            implicitHeight: 470
            // Keep maximized and tiled windows below the island's resting edge.
            exclusiveZone: Math.max(58, Math.min(92, (shell.pulse.settings?.island_height ?? 50) + 16))
            focusable: shell.sheetOpen
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
                readonly property int islandHeight: Math.max(42, Math.min(76, prefs.island_height ?? 50))
                height: shell.sheetOpen ? islandHeight + 350 : islandHeight
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 8

                Rectangle {
                    id: island
                    width: parent.width
                    height: clickSurface.islandHeight
                    radius: height / 2
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, (clickSurface.prefs.glass_opacity ?? 68) / 100)
                    border.width: 1
                    border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.30)

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.13) }
                            GradientStop { position: 0.46; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(shell.accent2.r, shell.accent2.g, shell.accent2.b, 0.12) }
                        }
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
                                width: shell.activeWorkspace === index + 1 ? 24 : 7
                                height: 7
                                radius: 4
                                color: shell.activeWorkspace === index + 1 ? shell.accent
                                      : Qt.rgba(shell.fg.r, shell.fg.g, shell.fg.b, 0.25)
                                Behavior on width { NumberAnimation { duration: Math.round(105 * shell.motionScale); easing.type: Easing.OutCubic } }
                                Behavior on color { ColorAnimation { duration: Math.round(90 * shell.motionScale) } }
                                TapHandler { onTapped: shell.activateWorkspace(index + 1) }
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
                            visible: !shell.pulse.playing
                            width: 9
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

                        Row {
                            id: visualizer
                            visible: shell.pulse.playing === true
                            anchors.centerIn: parent
                            spacing: 3
                            Repeater {
                                model: 9
                                Rectangle {
                                    required property int index
                                    width: 3
                                    height: 5 + 12 * Math.abs(Math.sin(shell.visualPhase + index * 0.72))
                                    radius: 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: index % 2 ? shell.accent2 : shell.accent
                                    Behavior on height { NumberAnimation { duration: 78; easing.type: Easing.OutCubic } }
                                }
                            }
                        }

                        Text {
                            anchors.right: shell.pulse.playing ? visualizer.left : droplet.left
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
                            anchors.left: shell.pulse.playing ? visualizer.right : droplet.right
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
                            width: 112; height: 32; radius: 16
                            color: controlsHover.hovered ? Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.18) : "transparent"
                            HoverHandler { id: controlsHover }
                            TapHandler { onTapped: shell.open("controls") }
                            Row {
                                anchors.centerIn: parent; spacing: 10
                                Item { width: 18; height: 28; Text { anchors.centerIn: parent; text: shell.pulse.network === "Offline" ? "󰖪" : "󰖩"; color: shell.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 14 } }
                                Item { width: 42; height: 28; Text { anchors.centerIn: parent; text: (shell.pulse.battery ?? -1) >= 0 ? shell.pulse.battery + "%" : (shell.pulse.cpu ?? 0) + "%"; color: shell.fg; font.family: "Inter"; font.pixelSize: 10; font.weight: Font.DemiBold } }
                                Item { width: 16; height: 28; Text { anchors.centerIn: parent; text: shell.sheetOpen ? "󰅃" : "󰅀"; color: shell.muted; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 12 } }
                            }
                        }
                    }
                }

                Rectangle {
                    id: sheetPanel
                    anchors.top: island.bottom
                    anchors.topMargin: 8
                    width: parent.width
                    height: 336
                    radius: 26
                    visible: opacity > 0.01
                    opacity: shell.sheetOpen ? 1 : 0
                    scale: shell.sheetOpen ? 1 : 0.985
                    transformOrigin: Item.Top
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, Math.min(0.94, ((clickSurface.prefs.glass_opacity ?? 68) + 10) / 100))
                    border.width: 1
                    border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.28)
                    clip: true

                    Behavior on opacity { NumberAnimation { duration: Math.round(125 * shell.motionScale); easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: Math.round(145 * shell.motionScale); easing.type: Easing.OutCubic } }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 14

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: shell.sheet === "wifi" ? "Wi-Fi" : shell.sheet === "bluetooth" ? "Bluetooth" : shell.sheet === "media" ? "Now playing" : "Controls"
                                color: shell.fg
                                font.family: "Inter"
                                font.pixelSize: 17
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: shell.sheet === "wifi" ? (Networking.wifiEnabled ? "On" : "Off") : shell.sheet === "bluetooth" ? (shell.bluetoothAdapter && shell.bluetoothAdapter.enabled ? "On" : "Off") : ""
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
                            visible: shell.sheet === "controls" || shell.sheet === "media"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 16

                            ColumnLayout {
                                Layout.preferredWidth: 236
                                spacing: 10
                                GlassAction { Layout.fillWidth: true; glyph: "󰖩"; label: shell.pulse.network ?? "Wi-Fi"; detail: "Networks"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.open("wifi") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰂯"; label: "Bluetooth"; detail: "Devices"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.open("bluetooth") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰂚"; label: "Notifications"; detail: "Open history"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("swaync-client --toggle-panel") }
                            }

                            Rectangle { Layout.fillHeight: true; width: 1; color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, 0.14) }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                FluidSlider {
                                    Layout.fillWidth: true; glyph: shell.pulse.muted ? "󰖁" : "󰕾"; motionScale: shell.motionScale
                                    value: (shell.pulse.volume ?? 0) / 100; foreground: shell.fg; accent: shell.accent
                                    onMoved: value => shell.run("wpctl set-volume -l 1.25 @DEFAULT_AUDIO_SINK@ " + Math.round(value * 100) + "%")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    GlassAction { Layout.fillWidth: true; glyph: shell.pulse.playing ? "󰏤" : "󰐊"; label: shell.pulse.playing ? "Pause" : "Play"; detail: shell.pulse.title || "No active player"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.run("playerctl play-pause") }
                                    GlassAction { Layout.fillWidth: true; glyph: "󰒓"; label: "Settings"; detail: "System controls"; foreground: shell.fg; muted: shell.muted; accent: shell.accent2; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("tempered-settings") }
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
                                GlassAction { Layout.fillWidth: true; glyph: "󰌾"; label: "Lock"; detail: "Secure session"; foreground: shell.fg; muted: shell.muted; accent: shell.accent; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("hyprlock") }
                                GlassAction { Layout.fillWidth: true; glyph: "󰐥"; label: "Power"; detail: "Session options"; foreground: shell.fg; muted: shell.muted; accent: shell.accent2; surface: shell.raised; motionScale: shell.motionScale; onTriggered: shell.launch("tempered-power") }
                                Text { text: "CPU " + (shell.pulse.cpu ?? 0) + "%  ·  RAM " + (shell.pulse.memory ?? 0) + "%"; color: shell.muted; font.family: "JetBrains Mono"; font.pixelSize: 9 }
                            }
                        }

                        ColumnLayout {
                            visible: shell.sheet === "wifi"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Wi-Fi"; color: shell.fg; font.family: "Inter"; font.pixelSize: 13; Layout.fillWidth: true }
                                Rectangle {
                                    width: 48; height: 25; radius: 13
                                    color: Networking.wifiEnabled ? shell.accent : shell.raised
                                    Rectangle { width: 19; height: 19; radius: 10; y: 3; x: Networking.wifiEnabled ? 26 : 3; color: Networking.wifiEnabled ? shell.bg : shell.muted; Behavior on x { NumberAnimation { duration: 100 } } }
                                    TapHandler { onTapped: Networking.wifiEnabled = !Networking.wifiEnabled }
                                }
                                Text { text: "Scan"; color: shell.accent; font.family: "Inter"; font.pixelSize: 11; TapHandler { onTapped: if (shell.wifiDevice) shell.wifiDevice.scannerEnabled = true } }
                            }

                            ListView {
                                id: wifiList
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 5
                                clip: true
                                model: shell.wifiDevice ? shell.wifiDevice.networks : null
                                delegate: Rectangle {
                                    required property var modelData
                                    width: wifiList.width; height: 43; radius: 14
                                    color: modelData.connected ? Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.20) : wifiHover.hovered ? Qt.rgba(shell.raised.r, shell.raised.g, shell.raised.b, 0.72) : "transparent"
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 13; anchors.rightMargin: 13
                                        Text { text: modelData.connected ? "󰤨" : modelData.security === WifiSecurityType.Open ? "󰤨" : "󰤪"; color: modelData.connected ? shell.accent : shell.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 14 }
                                        Text { text: modelData.name; color: shell.fg; font.family: "Inter"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                                        Text { text: modelData.connected ? "Connected" : Math.round(modelData.signalStrength * 100) + "%"; color: shell.muted; font.family: "Inter"; font.pixelSize: 10 }
                                    }
                                    HoverHandler { id: wifiHover }
                                    TapHandler {
                                        onTapped: {
                                            if (modelData.connected) modelData.disconnect()
                                            else if (modelData.known || modelData.security === WifiSecurityType.Open) modelData.connect()
                                            else { shell.passwordNetwork = modelData; wifiPassword.forceActiveFocus() }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                visible: shell.passwordNetwork !== null
                                Layout.fillWidth: true; height: 40; radius: 13
                                color: Qt.rgba(shell.raised.r, shell.raised.g, shell.raised.b, 0.76)
                                RowLayout {
                                    anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 8
                                    TextInput { id: wifiPassword; Layout.fillWidth: true; color: shell.fg; font.family: "Inter"; font.pixelSize: 12; echoMode: TextInput.Password; clip: true; Text { visible: wifiPassword.text.length === 0; text: "Password for " + (shell.passwordNetwork ? shell.passwordNetwork.name : "network"); color: shell.muted; font: wifiPassword.font } }
                                    Text { text: "Join"; color: shell.accent; font.family: "Inter"; font.pixelSize: 11; TapHandler { onTapped: { if (shell.passwordNetwork && wifiPassword.text.length) shell.passwordNetwork.connectWithPsk(wifiPassword.text); wifiPassword.text = ""; shell.passwordNetwork = null } } }
                                }
                            }
                        }

                        ColumnLayout {
                            visible: shell.sheet === "bluetooth"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Bluetooth"; color: shell.fg; font.family: "Inter"; font.pixelSize: 13; Layout.fillWidth: true }
                                Rectangle {
                                    width: 48; height: 25; radius: 13
                                    color: shell.bluetoothAdapter && shell.bluetoothAdapter.enabled ? shell.accent : shell.raised
                                    Rectangle { width: 19; height: 19; radius: 10; y: 3; x: shell.bluetoothAdapter && shell.bluetoothAdapter.enabled ? 26 : 3; color: shell.bluetoothAdapter && shell.bluetoothAdapter.enabled ? shell.bg : shell.muted; Behavior on x { NumberAnimation { duration: 100 } } }
                                    TapHandler { onTapped: if (shell.bluetoothAdapter) shell.bluetoothAdapter.enabled = !shell.bluetoothAdapter.enabled }
                                }
                                Text { text: shell.bluetoothAdapter && shell.bluetoothAdapter.discovering ? "Scanning…" : "Scan"; color: shell.accent; font.family: "Inter"; font.pixelSize: 11; TapHandler { onTapped: if (shell.bluetoothAdapter) shell.bluetoothAdapter.discovering = !shell.bluetoothAdapter.discovering } }
                            }

                            ListView {
                                id: bluetoothList
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 5
                                clip: true
                                model: shell.bluetoothAdapter ? shell.bluetoothAdapter.devices : null
                                delegate: Rectangle {
                                    required property var modelData
                                    width: bluetoothList.width; height: 45; radius: 14
                                    color: modelData.connected ? Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.20) : btHover.hovered ? Qt.rgba(shell.raised.r, shell.raised.g, shell.raised.b, 0.72) : "transparent"
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 13; anchors.rightMargin: 13
                                        Text { text: "󰂯"; color: modelData.connected ? shell.accent : shell.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 15 }
                                        ColumnLayout { Layout.fillWidth: true; spacing: 0; Text { text: modelData.name || modelData.deviceName; color: shell.fg; font.family: "Inter"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight } Text { text: modelData.connected ? "Connected" : modelData.paired ? "Paired" : "Nearby"; color: shell.muted; font.family: "Inter"; font.pixelSize: 9 } }
                                        Text { visible: modelData.batteryAvailable; text: Math.round(modelData.battery * 100) + "%"; color: shell.muted; font.family: "Inter"; font.pixelSize: 10 }
                                    }
                                    HoverHandler { id: btHover }
                                    TapHandler { onTapped: { if (modelData.connected) modelData.disconnect(); else if (modelData.paired) modelData.connect(); else modelData.pair() } }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
