import QtQuick

Rectangle {
    id: root
    property string glyph: ""
    property string label: ""
    property string detail: ""
    property color foreground: "white"
    property color muted: "#aab3c2"
    property color accent: "#87bfff"
    property color surface: "#242b38"
    property bool active: false
    property real motionScale: 1
    signal triggered()

    implicitWidth: 152
    implicitHeight: 52
    radius: 17
    color: active ? Qt.rgba(accent.r, accent.g, accent.b, 0.22)
                  : Qt.rgba(surface.r, surface.g, surface.b, hover.hovered ? 0.76 : 0.54)
    border.width: 1
    border.color: active ? Qt.rgba(accent.r, accent.g, accent.b, 0.68)
                         : Qt.rgba(foreground.r, foreground.g, foreground.b, 0.10)
    scale: tap.pressed ? 0.965 : 1

    Behavior on color { ColorAnimation { duration: Math.round(190 * root.motionScale) } }
    Behavior on scale { NumberAnimation { duration: Math.round(115 * root.motionScale); easing.type: Easing.OutCubic } }

    HoverHandler { id: hover }
    TapHandler { id: tap; onTapped: root.triggered() }

    Row {
        anchors.fill: parent
        anchors.margins: 11
        spacing: 10

        Text {
            width: 24
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter
            text: root.glyph
            color: root.active ? root.accent : root.foreground
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 17
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 36
            spacing: 1
            Text {
                width: parent.width
                text: root.label
                color: root.foreground
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                visible: text.length > 0
                text: root.detail
                color: root.muted
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 9
            }
        }
    }
}
