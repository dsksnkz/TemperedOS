import QtQuick

Item {
    id: root
    property real modelValue: 0.5
    property real visualValue: modelValue
    property string glyph: ""
    property color foreground: "white"
    property color accent: "#87bfff"
    property real motionScale: 1
    signal moved(real value)

    onModelValueChanged: if (!drag.active) visualValue = modelValue

    implicitWidth: 220
    implicitHeight: 32

    Text {
        id: icon
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 24
        text: root.glyph
        color: root.foreground
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 15
    }

    Rectangle {
        id: track
        anchors.left: icon.right
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: 7
        radius: 4
        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)

        Rectangle {
            width: Math.max(height, parent.width * Math.max(0, Math.min(1, root.visualValue)))
            height: parent.height
            radius: parent.radius
            color: root.accent
            Behavior on width { NumberAnimation { duration: Math.round(55 * root.motionScale); easing.type: Easing.OutCubic } }
        }

        Rectangle {
            x: Math.max(0, Math.min(parent.width - width, parent.width * root.visualValue - width / 2))
            anchors.verticalCenter: parent.verticalCenter
            width: drag.active ? 16 : 12
            height: width
            radius: width / 2
            color: root.foreground
            Behavior on width { NumberAnimation { duration: Math.round(100 * root.motionScale) } }
        }

        MouseArea {
            id: drag
            anchors.fill: parent
            property bool active: pressed
            onPressed: update(mouse.x)
            onPositionChanged: if (pressed) update(mouse.x)
            function update(px) {
                root.visualValue = Math.max(0, Math.min(1, px / width))
                root.moved(root.visualValue)
            }
        }
    }
}
