import QtQuick

Rectangle {
    id: root
    required property var theme
    property string text: ""
    property string glyph: ""
    property bool selected: false
    property bool compact: false
    signal triggered()
    implicitWidth: content.width + (compact ? 24 : 30)
    implicitHeight: compact ? 30 : 36
    radius: height / 2
    color: selected ? theme.accent : Qt.rgba(theme.fg.r, theme.fg.g, theme.fg.b, hover.hovered ? 0.12 : 0.045)
    opacity: enabled ? 1 : 0.38
    scale: tap.pressed ? 0.96 : 1
    border.width: selected ? 0 : 1
    border.color: Qt.rgba(theme.fg.r, theme.fg.g, theme.fg.b, 0.08)
    Behavior on color { ColorAnimation { duration: 120 * root.theme.motionScale } }
    Behavior on scale { NumberAnimation { duration: 100 * root.theme.motionScale; easing.type: Easing.OutCubic } }
    Row {
        id: content
        anchors.centerIn: parent
        spacing: 7
        Text { visible: root.glyph !== ""; text: root.glyph; color: root.selected ? root.theme.bg : root.theme.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
        Text { visible: root.text !== ""; text: root.text; color: root.selected ? root.theme.bg : root.theme.fg; font.family: "Inter"; font.pixelSize: 11; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: root.triggered() }
    Accessible.role: Accessible.Button
    Accessible.name: text
}
