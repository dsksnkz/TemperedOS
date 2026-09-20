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
    signal committed(real value)

    onModelValueChanged: if (!drag.pressed) { settle.stop(); visualValue = modelValue }
    Timer { id: settle; interval: 3000; onTriggered: root.visualValue = root.modelValue }

    implicitWidth: 220
    implicitHeight: 32

    Text {
        id: icon
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: root.glyph ? 24 : 0
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
            width: drag.pressed ? 16 : 12
            height: width
            radius: width / 2
            color: root.foreground
            Behavior on width { NumberAnimation { duration: Math.round(100 * root.motionScale) } }
        }

    }
    MouseArea {
        id: drag
        anchors.left: icon.right; anchors.right: parent.right
        anchors.top: parent.top; anchors.bottom: parent.bottom
        cursorShape: Qt.PointingHandCursor
        onPressed: mouse => { settle.stop(); update(mouse.x) }
        onPositionChanged: mouse => { if (pressed) update(mouse.x) }
        onReleased: { settle.restart(); root.committed(root.visualValue) }
        onCanceled: root.visualValue = root.modelValue
        function update(px) {
            root.visualValue = Math.max(0, Math.min(1, px / width))
            root.moved(root.visualValue)
        }
    }
}
