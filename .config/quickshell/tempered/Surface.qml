import QtQuick

Rectangle {
    required property var theme
    radius: 22
    color: Qt.rgba(theme.raised.r, theme.raised.g, theme.raised.b, 0.38)
    border.width: 1
    border.color: Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.12)
}
