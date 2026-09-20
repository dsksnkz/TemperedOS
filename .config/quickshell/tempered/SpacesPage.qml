import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland

ColumnLayout {
    id: root
    required property var theme
    spacing: 12
    GridLayout {
        columns: 3
        rowSpacing: 10; columnSpacing: 10
        Layout.fillWidth: true; Layout.fillHeight: true
        Repeater {
            model: Hyprland.workspaces.values.filter(w => w.id > 0).sort((a,b) => a.id - b.id).slice(0, 9)
            Surface {
                id: space
                required property var modelData
                theme: root.theme
                Layout.fillWidth: true; Layout.fillHeight: true
                border.color: modelData.focused ? root.theme.accent : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, .12)
                color: spaceHover.hovered ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, .13) : Qt.rgba(root.theme.raised.r, root.theme.raised.g, root.theme.raised.b, .38)
                HoverHandler { id: spaceHover }
                TapHandler { onTapped: { space.modelData.activate(); root.theme.sheetOpen = false } }
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 13; spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: String(space.modelData.id).padStart(2,"0"); color: space.modelData.focused ? root.theme.accent : root.theme.fg; font.family: "Inter"; font.pixelSize: 21; font.weight: Font.Light; Layout.fillWidth: true }
                        Text { text: space.modelData.toplevels.values.length + " open"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9 }
                    }
                    Repeater {
                        model: space.modelData.toplevels.values.slice(0, 2)
                        Text {
                            required property var modelData
                            text: modelData.title || "Window"; Layout.fillWidth: true; elide: Text.ElideRight
                            color: root.theme.fg; font.family: "Inter"; font.pixelSize: 10
                            TapHandler { onTapped: { root.theme.focusWindow(modelData); root.theme.sheetOpen = false } }
                        }
                    }
                    Text { visible: space.modelData.toplevels.values.length === 0; text: "A fresh space"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10 }
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Your work, with room to breathe."; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10; Layout.fillWidth: true }
        Pill { theme: root.theme; text: "Find a window"; compact: true; onTriggered: root.theme.launch("~/.local/bin/tempered-launcher --windows") }
    }
}
