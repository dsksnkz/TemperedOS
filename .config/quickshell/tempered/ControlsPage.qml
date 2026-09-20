import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Pipewire

RowLayout {
    id: root
    required property var theme
    spacing: 12

    ColumnLayout {
        Layout.preferredWidth: 210
        Layout.minimumWidth: 180
        Layout.maximumWidth: 210
        Layout.fillHeight: true
        spacing: 9
        GlassAction { Layout.fillWidth: true; glyph: "󰖩"; label: root.theme.pulse.network ?? "Network"; detail: "Wi-Fi & connections"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.open("wifi") }
        GlassAction { Layout.fillWidth: true; glyph: "󰂯"; label: "Bluetooth"; detail: "Your nearby devices"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.open("bluetooth") }
        GlassAction { Layout.fillWidth: true; glyph: "󰂚"; label: "Notifications"; detail: "Catch up in your own time"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.launch("swaync-client --toggle-panel") }
        GlassAction { Layout.fillWidth: true; glyph: "󰒓"; label: "Settings"; detail: "Make this space yours"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.launch("~/.local/bin/tempered-settings") }
        Item { Layout.fillHeight: true }
    }
    ColumnLayout {
        Layout.preferredWidth: 420
        Layout.minimumWidth: 290
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 10
        Surface {
            theme: root.theme
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Sound & light"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    Pill { theme: root.theme; glyph: root.theme.mic?.audio?.muted ? "󰍭" : "󰍬"; text: root.theme.mic?.audio?.muted ? "Mic off" : "Mic"; compact: true; enabled: !!root.theme.mic?.audio; onTriggered: root.theme.mic.audio.muted = !root.theme.mic.audio.muted }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Pill { theme: root.theme; glyph: root.theme.audio?.muted ? "󰖁" : "󰕾"; compact: true; enabled: !!root.theme.audio; onTriggered: root.theme.audio.muted = !root.theme.audio.muted }
                    FluidSlider { Layout.fillWidth: true; modelValue: root.theme.volume; motionScale: root.theme.motionScale; foreground: root.theme.fg; accent: root.theme.accent; enabled: !!root.theme.audio; onMoved: value => { if (root.theme.audio) root.theme.audio.volume = value } }
                    Text { text: Math.round(root.theme.volume * 100) + "%"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 11; Layout.preferredWidth: 37; horizontalAlignment: Text.AlignRight }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Pill { theme: root.theme; glyph: "󰃠"; compact: true; onTriggered: root.theme.launch("~/.local/bin/tempered-settings --page displays") }
                    FluidSlider { Layout.fillWidth: true; modelValue: (root.theme.pulse.brightness ?? 50) / 100; motionScale: root.theme.motionScale; foreground: root.theme.fg; accent: root.theme.accent2; onCommitted: value => root.theme.setBrightness(Math.max(5, Math.round(value * 100))) }
                    Text { text: (root.theme.pulse.brightness ?? 50) + "%"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 11; Layout.preferredWidth: 37; horizontalAlignment: Text.AlignRight }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Qt.rgba(root.theme.fg.r, root.theme.fg.g, root.theme.fg.b, .08) }
                Text { visible: !!root.theme.pulse.brightnessError; text: root.theme.pulse.brightnessError ?? ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.theme.accent2; font.family: "Inter"; font.pixelSize: 10 }
                Text { text: "OUTPUT"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9; font.letterSpacing: 1; Layout.topMargin: 5 }
                ListView {
                    id: outputs
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; spacing: 3
                    model: Pipewire.nodes.values.filter(n => n.audio && n.isSink && !n.isStream)
                    delegate: Rectangle {
                        required property var modelData
                        width: outputs.width; height: 34; radius: 10
                        color: root.theme.sink === modelData ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, .18) : outputHover.hovered ? Qt.rgba(root.theme.fg.r, root.theme.fg.g, root.theme.fg.b, .05) : "transparent"
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
                            Text { text: modelData.nickname || modelData.description || modelData.name; elide: Text.ElideRight; Layout.fillWidth: true; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 10 }
                            Text { text: root.theme.sink === modelData ? "✓" : ""; color: root.theme.accent; font.pixelSize: 13 }
                        }
                        HoverHandler { id: outputHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: Pipewire.preferredDefaultAudioSink = modelData }
                    }
                    Text { anchors.centerIn: parent; visible: outputs.count === 0; text: "No sound outputs connected"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 11 }
                }
            }
        }
    }
    ColumnLayout {
        Layout.preferredWidth: 160
        Layout.minimumWidth: 150
        Layout.maximumWidth: 180
        Layout.fillHeight: true
        spacing: 9
        GlassAction { Layout.fillWidth: true; glyph: "󰹑"; label: "Capture"; detail: "Area → clipboard & file"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.launch("~/.local/bin/tempered-capture") }
        GlassAction { Layout.fillWidth: true; glyph: "󰀻"; label: "Apps"; detail: "Find something to do"; foreground: root.theme.fg; muted: root.theme.muted; accent: root.theme.accent; surface: root.theme.raised; motionScale: root.theme.motionScale; onTriggered: root.theme.launch("~/.local/bin/tempered-launcher") }
        RowLayout {
            Layout.fillWidth: true
            Pill { theme: root.theme; glyph: "󰌾"; text: "Lock"; Layout.fillWidth: true; onTriggered: root.theme.launch("hyprlock") }
            Pill { theme: root.theme; glyph: "󰐥"; onTriggered: root.theme.powerMenu() }
        }
        Item { Layout.fillHeight: true }
        Text { text: "SYSTEM AT A GLANCE"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 8; font.letterSpacing: .8 }
        Repeater {
            model: [{label: "Processor", value: root.theme.pulse.cpu ?? 0}, {label: "Memory", value: root.theme.pulse.memory ?? 0}]
            ColumnLayout {
                required property var modelData
                Layout.fillWidth: true; spacing: 6
                RowLayout { Layout.fillWidth: true; Text { text: modelData.label; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10; Layout.fillWidth: true } Text { text: modelData.value + "%"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 10 } }
                Rectangle { Layout.fillWidth: true; height: 3; radius: 2; color: Qt.rgba(root.theme.fg.r, root.theme.fg.g, root.theme.fg.b, .08); Rectangle { width: parent.width * Math.min(1, modelData.value / 100); height: 3; radius: 2; color: root.theme.accent; Behavior on width { NumberAnimation { duration: 300 * root.theme.motionScale } } } }
            }
        }
    }
}
