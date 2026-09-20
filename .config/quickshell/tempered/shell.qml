//@ pragma ShellId tempered-shell
//@ pragma DropExpensiveFonts

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Mpris
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Wayland

ShellRoot {
    id: shell
    property bool sheetOpen: false
    property string sheet: "controls"
    property string sheetScreen: ""
    property var pulse: ({})
    property var palette: ({background: "#121923", surface: "#202b39", surfaceRaised: "#2d3948", text: "#eef5ff", muted: "#aabaca", accent: "#7ebeff", accent2: "#9a92ff", border: "#b6d4ef"})
    readonly property color bg: palette.background ?? "#121923"
    readonly property color surface: palette.surface ?? "#202b39"
    readonly property color raised: palette.surfaceRaised ?? "#2d3948"
    readonly property color fg: palette.text ?? "#eef5ff"
    readonly property color muted: palette.muted ?? "#aabaca"
    readonly property color accent: palette.accent ?? "#7ebeff"
    readonly property color accent2: palette.accent2 ?? "#9a92ff"
    readonly property color border: palette.border ?? "#b6d4ef"
    readonly property var prefs: pulse.settings ?? ({})
    readonly property string userName: prefs.display_name || pulse.user || "You"
    readonly property int activeWorkspace: Hyprland.focusedWorkspace?.id ?? 1
    readonly property real motionScale: prefs.reduce_motion || prefs.animations === false ? 0 : Math.max(.5, Math.min(2, 100 / (prefs.animation_speed ?? 100)))
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var mic: Pipewire.defaultAudioSource
    readonly property var audio: sink?.audio ?? null
    readonly property real volume: audio?.volume ?? 0
    property var preferredPlayer: null
    readonly property var player: {
        const players = Mpris.players.values
        if (preferredPlayer && players.includes(preferredPlayer)) return preferredPlayer
        return players.find(p => p.isPlaying) || players[0] || null
    }
    readonly property bool playing: player?.isPlaying ?? false
    property var spectrum: [0,0,0,0,0,0,0,0]
    property string feedback: ""
    property bool feedbackReady: false

    function open(name, screenName) {
        if (sheetOpen && sheet === name) { sheetOpen = false; return }
        sheet = name
        sheetScreen = screenName || Hyprland.focusedMonitor?.name || ""
        sheetOpen = true
        if (name === "spaces") Hyprland.refreshToplevels()
    }
    function run(command) { Quickshell.execDetached(["sh", "-lc", command]) }
    function launch(command) { sheetOpen = false; launchDelay.command = command; launchDelay.restart() }
    function powerMenu() { launch("~/.local/bin/tempered-power") }
    function activateWorkspace(id) {
        const existing = Hyprland.workspaces.values.find(w => w.id === id)
        if (existing) existing.activate()
        else Hyprland.dispatch(Hyprland.usingLua ? "hl.dsp.focus({workspace=" + Number(id) + "})" : "workspace " + Number(id))
    }
    function focusWindow(window) {
        if (window.wayland) window.wayland.activate()
        else Hyprland.dispatch(Hyprland.usingLua ? "hl.dsp.focus({window='address:0x" + window.address.replace(/^0x/, "") + "'})" : "focuswindow address:0x" + window.address.replace(/^0x/, ""))
    }
    function showFeedback(text) { if (feedbackReady && prefs.island_feedback !== false) { feedback = text; feedbackTimer.restart() } }
    function setBrightness(value) { run("~/.local/bin/tempered-brightness set " + value); showFeedback("Brightness  " + value + "%") }
    onVolumeChanged: showFeedback("Volume  " + Math.round(volume * 100) + "%")
    Connections { target: shell.audio; function onMutedChanged() { shell.showFeedback(shell.audio.muted ? "Sound muted" : "Sound on") } }

    DeskService { id: deskService }
    PwObjectTracker { objects: [shell.sink, shell.mic].filter(Boolean) }
    SystemClock { id: clock; precision: SystemClock.Seconds }
    Timer { interval: 2500; running: true; onTriggered: shell.feedbackReady = true }
    Timer { id: feedbackTimer; interval: 1500; onTriggered: shell.feedback = "" }
    Timer { id: launchDelay; property string command: ""; interval: 130; onTriggered: shell.run(command) }
    Process {
        command: ["python3", Quickshell.shellPath("status.py")]
        running: true
        stdout: SplitParser {
            onRead: data => {
                try { const next = JSON.parse(data); shell.pulse = next; if (next.palette?.accent) shell.palette = next.palette }
                catch (error) { console.warn("Status:", error) }
            }
        }
    }
    Process {
        command: ["cava", "-p", Quickshell.shellPath("cava.conf")]
        running: shell.playing && shell.prefs.music_visualizer !== false && shell.motionScale > 0
        stdout: SplitParser {
            onRead: data => {
                const values = data.split(";").slice(0,8).map(v => Math.max(0, Math.min(100, Number(v) || 0)))
                if (values.length === 8) shell.spectrum = values
            }
        }
    }
    IpcHandler {
        target: "tempered"
        function toggle(): void { shell.open("controls") }
        function controls(): void { shell.open("controls") }
        function desk(): void { shell.open("desk") }
        function spaces(): void { shell.open("spaces") }
        function media(): void { shell.open("media") }
        function wifi(): void { shell.open("wifi") }
        function bluetooth(): void { shell.open("bluetooth") }
        function recolor(): void { /* status feed observes palette file */ }
        function close(): void { shell.sheetOpen = false }
        function power(): void { shell.powerMenu() }
        function diagnostics(): string { return JSON.stringify({page: shell.sheet, open: shell.sheetOpen, audioReady: !!shell.audio, volume: shell.volume, deskReady: deskService.ready, playerCount: Mpris.players.values.length, workspaceCount: Hyprland.workspaces.values.length, tray: SystemTray.items.values.map(i => ({id: i.id, title: i.title, icon: i.icon}))}) }
    }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: window
            required property var modelData
            screen: modelData
            readonly property bool expanded: shell.sheetOpen && (!shell.sheetScreen || shell.sheetScreen === screen.name)
            color: "transparent"
            implicitHeight: Math.min(screen.height, 520)
            exclusiveZone: Math.max(58, Math.min(92, (shell.prefs.island_height ?? 50) + 16))
            focusable: expanded
            WlrLayershell.namespace: "tempered-island"
            anchors { top: true; left: true; right: true }
            mask: Region { item: clickSurface; radius: 25 }
            HyprlandFocusGrab { windows: [window]; active: window.expanded; onCleared: shell.sheetOpen = false }
            Shortcut { sequence: "Escape"; enabled: window.expanded; onActivated: shell.sheetOpen = false }

            Item {
                id: clickSurface
                width: Math.min(window.width - 24, Math.max(820, Math.min(window.width * ((shell.prefs.island_width ?? 50) / 100), 1160)))
                readonly property int islandHeight: Math.max(42, Math.min(76, shell.prefs.island_height ?? 50))
                height: window.expanded ? islandHeight + sheetPanel.height + 8 : islandHeight
                anchors.horizontalCenter: parent.horizontalCenter
                y: 8

                Rectangle {
                    id: island
                    width: parent.width; height: clickSurface.islandHeight; radius: height / 2
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, Math.max(.72, (shell.prefs.glass_opacity ?? 68) / 100))
                    border.width: 1; border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, .3)
                    Rectangle {
                        anchors.fill: parent; anchors.margins: 1; radius: parent.radius - 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, .14) }
                            GradientStop { position: .5; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(shell.accent2.r, shell.accent2.g, shell.accent2.b, .1) }
                        }
                    }
                    Row {
                        id: workspaces
                        anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        spacing: 1
                        Pill { theme: shell; glyph: "󰠮"; compact: true; selected: window.expanded && shell.sheet === "desk"; onTriggered: shell.open("desk", window.screen.name) }
                        Repeater {
                            model: 6
                            Item {
                                required property int index
                                width: 24; height: 32
                                Rectangle {
                                    anchors.centerIn: parent
                                    width: shell.activeWorkspace === index + 1 ? 20 : 5
                                    height: shell.activeWorkspace === index + 1 ? 7 : 5
                                    radius: 4
                                    color: shell.activeWorkspace === index + 1 ? shell.accent : spaceHover.hovered ? shell.fg : Qt.rgba(shell.fg.r, shell.fg.g, shell.fg.b, .3)
                                    Behavior on width { NumberAnimation { duration: 110 * shell.motionScale; easing.type: Easing.OutCubic } }
                                }
                                HoverHandler { id: spaceHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { acceptedButtons: Qt.LeftButton | Qt.RightButton; onTapped: (eventPoint, button) => { if (button === Qt.RightButton) shell.open("spaces", window.screen.name); else shell.activateWorkspace(index + 1) } }
                            }
                        }
                    }
                    Item {
                        anchors.centerIn: parent; width: Math.max(190, parent.width - 580); height: parent.height
                        Row {
                            anchors.centerIn: parent; spacing: 11
                            Text { visible: !shell.feedback; text: deskService.active ? "FOCUS" : shell.playing ? (shell.player?.trackArtist || "Playing") : Qt.formatDateTime(clock.date, "ddd d MMM"); color: shell.muted; font.family: "Inter"; font.pixelSize: 10; elide: Text.ElideRight; width: Math.min(110, implicitWidth); anchors.verticalCenter: parent.verticalCenter }
                            Item {
                                width: shell.playing && !deskService.active && !shell.feedback ? 38 : 12; height: 24
                                Rectangle { anchors.centerIn: parent; width: 7; height: 7; radius: 4; color: shell.accent; visible: !shell.playing || deskService.active || !!shell.feedback }
                                Row {
                                    visible: shell.playing && !deskService.active && !shell.feedback; anchors.centerIn: parent; spacing: 2
                                    Repeater { model: 8; Rectangle { required property int index; width: 3; height: 3 + (shell.prefs.music_visualizer === false || shell.motionScale === 0 ? 0 : (shell.spectrum[index] ?? 0) * .17); radius: 2; anchors.verticalCenter: parent.verticalCenter; color: index % 2 ? shell.accent2 : shell.accent; Behavior on height { NumberAnimation { duration: 50; easing.type: Easing.OutCubic } } } }
                                }
                            }
                            Text { text: shell.feedback || (deskService.active ? deskService.timeLeft : shell.playing ? (shell.player?.trackTitle || "Now playing") : Qt.formatDateTime(clock.date, shell.prefs.show_seconds ? "HH:mm:ss" : "HH:mm")); color: shell.fg; font.family: "Inter"; font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight; width: Math.min(shell.feedback ? 180 : 132, implicitWidth); anchors.verticalCenter: parent.verticalCenter }
                        }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: shell.open(deskService.active ? "desk" : shell.playing ? "media" : "desk", window.screen.name) }
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 3
                        Repeater {
                            model: shell.prefs.island_compact ? [] : SystemTray.items.values.slice(0,5)
                            Item {
                                required property var modelData
                                readonly property bool anonymousQtItem: !modelData.title && modelData.id.startsWith("systray_")
                                width: 24; height: 32
                                Image { id: trayIcon; anchors.centerIn: parent; width: 16; height: 16; source: parent.anonymousQtItem ? "" : modelData.icon; visible: status === Image.Ready }
                                Text { anchors.centerIn: parent; visible: parent.anonymousQtItem || trayIcon.status !== Image.Ready; text: (modelData.title || "◇").charAt(0).toUpperCase(); color: shell.fg; font.family: "Inter"; font.pixelSize: 13 }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                                TapHandler { acceptedButtons: Qt.LeftButton | Qt.RightButton; onTapped: (eventPoint, button) => { if ((modelData.onlyMenu || button === Qt.RightButton) && modelData.hasMenu) modelData.display(window, window.width - 100, 50); else modelData.activate() } }
                            }
                        }
                        Pill { theme: shell; text: (shell.pulse.battery ?? -1) >= 0 ? shell.pulse.battery + "%" : "Controls"; glyph: "󰒓"; compact: true; selected: window.expanded && shell.sheet === "controls"; onTriggered: shell.open("controls", window.screen.name) }
                    }
                }
                Rectangle {
                    id: sheetPanel
                    y: island.height + 8
                    width: parent.width
                    height: Math.min(406, window.height - island.height - 22)
                    radius: 27
                    visible: opacity > .01
                    opacity: window.expanded ? 1 : 0
                    scale: window.expanded ? 1 : .975
                    transformOrigin: Item.Top
                    color: Qt.rgba(shell.surface.r, shell.surface.g, shell.surface.b, .95)
                    border.width: 1; border.color: Qt.rgba(shell.border.r, shell.border.g, shell.border.b, .28)
                    Behavior on opacity { NumberAnimation { duration: 130 * shell.motionScale; easing.type: Easing.OutCubic } }
                    Behavior on scale { NumberAnimation { duration: 170 * shell.motionScale; easing.type: Easing.OutCubic } }
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 18; spacing: 14
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Rectangle {
                                width: 33; height: 33; radius: 17; color: Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, .2)
                                Text { anchors.centerIn: parent; text: shell.userName.charAt(0).toUpperCase(); color: shell.accent; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold }
                                TapHandler { onTapped: shell.launch("~/.local/bin/tempered-settings") }
                            }
                            ColumnLayout { spacing: 1; Layout.preferredWidth: 120; Layout.maximumWidth: 160; Text { text: shell.userName; Layout.fillWidth: true; elide: Text.ElideRight; color: shell.fg; font.family: "Inter"; font.pixelSize: 12; font.weight: Font.DemiBold } Text { text: "A space of your own"; color: shell.muted; font.family: "Inter"; font.pixelSize: 9 } }
                            Item { Layout.fillWidth: true }
                            Repeater {
                                model: [{key: "desk", label: "Desk"}, {key: "controls", label: "Controls"}, {key: "media", label: "Sound"}, {key: "spaces", label: "Spaces"}]
                                Pill { required property var modelData; theme: shell; text: modelData.label; compact: true; selected: shell.sheet === modelData.key; onTriggered: { shell.sheet = modelData.key; if (modelData.key === "spaces") Hyprland.refreshToplevels() } }
                            }
                            Pill { theme: shell; text: "×"; compact: true; onTriggered: shell.sheetOpen = false }
                        }
                        DeskPage { theme: shell; desk: deskService; now: clock.date; visible: shell.sheet === "desk"; Layout.fillWidth: true; Layout.fillHeight: true }
                        ControlsPage { theme: shell; visible: shell.sheet === "controls"; Layout.fillWidth: true; Layout.fillHeight: true }
                        MediaPage { theme: shell; visible: shell.sheet === "media" && window.expanded; Layout.fillWidth: true; Layout.fillHeight: true }
                        SpacesPage { theme: shell; visible: shell.sheet === "spaces"; Layout.fillWidth: true; Layout.fillHeight: true }
                        ConnectionsPage { theme: shell; wifi: shell.sheet === "wifi"; visible: (shell.sheet === "wifi" || shell.sheet === "bluetooth") && window.expanded; Layout.fillWidth: true; Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
