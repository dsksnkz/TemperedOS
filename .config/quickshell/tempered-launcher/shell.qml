//@ pragma ShellId tempered-launcher
//@ pragma AppId io.github.dsksnkz.TemperedOS.Launcher

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets

FloatingWindow {
    id: root
    visible: true
    title: "Tempered Launcher"
    color: "transparent"
    implicitWidth: 780
    implicitHeight: 520

    property int mode: 0
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
    readonly property string needle: search.text.trim().toLowerCase()
    readonly property var apps: DesktopEntries.applications.values
        .filter(entry => !entry.noDisplay && (needle.length === 0 || entry.name.toLowerCase().includes(needle) || entry.comment.toLowerCase().includes(needle)))
        .sort((left, right) => left.name.localeCompare(right.name))
    readonly property var windows: Hyprland.toplevels.values
        .filter(item => item.title && (needle.length === 0 || item.title.toLowerCase().includes(needle)))
    readonly property var results: mode === 0 ? apps : windows

    function activateCurrent() {
        if (results.length === 0)
            return
        const target = results[Math.max(0, Math.min(results.length - 1, resultList.currentIndex))]
        if (mode === 0)
            target.execute()
        else
            target.activate()
        Qt.quit()
    }

    onVisibleChanged: if (!visible) Qt.quit()

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
    Shortcut { sequence: "Tab"; onActivated: { root.mode = (root.mode + 1) % 2; resultList.currentIndex = 0 } }

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
                        Keys.onTabPressed: { root.mode = (root.mode + 1) % 2; resultList.currentIndex = 0 }
                        Text { visible: search.text.length === 0; text: root.mode === 0 ? "Search applications" : "Search open windows"; color: root.muted; font: search.font }
                    }
                    Text { text: "esc"; color: root.muted; font.family: "JetBrains Mono"; font.pixelSize: 10 }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: ["Applications", "Windows"]
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
                Text { text: root.results.length + (root.results.length === 1 ? " result" : " results"); color: root.muted; font.family: "Inter"; font.pixelSize: 10 }
            }

            ListView {
                id: resultList
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
                            IconImage {
                                visible: root.mode === 0
                                anchors.centerIn: parent
                                implicitSize: 25
                                source: root.mode === 0 ? Quickshell.iconPath(modelData.icon) : ""
                            }
                            Text { visible: root.mode === 1; anchors.centerIn: parent; text: "󰖲"; color: root.accent; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 15 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { text: root.mode === 0 ? modelData.name : modelData.title; color: root.fg; font.family: "Inter"; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: root.mode === 0 ? (modelData.comment || modelData.genericName || "Application") : "Open window"; color: root.muted; font.family: "Inter"; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
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

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "↑↓ move    ↵ open    tab switch"
                color: root.muted
                font.family: "JetBrains Mono"
                font.pixelSize: 9
            }
        }
    }
}
