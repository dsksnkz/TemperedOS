import QtQuick
import QtQuick.Layouts

Surface {
    id: root
    required property date today
    property int offset: 0
    readonly property date month: new Date(today.getFullYear(), today.getMonth() + offset, 1)
    readonly property int firstDay: (month.getDay() + 6) % 7
    readonly property int days: new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 9
        RowLayout {
            Layout.fillWidth: true
            Text { text: Qt.formatDateTime(root.month, "MMMM yyyy"); color: root.theme.fg; font.family: "Inter"; font.pixelSize: 13; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Pill { theme: root.theme; text: "‹"; compact: true; onTriggered: root.offset-- }
            Pill { theme: root.theme; text: "›"; compact: true; onTriggered: root.offset++ }
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 7
            rowSpacing: 3
            columnSpacing: 3
            Repeater {
                model: ["M", "T", "W", "T", "F", "S", "S"]
                Text { required property string modelData; text: modelData; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9; Layout.preferredHeight: 16 }
            }
            Repeater {
                model: 42
                Rectangle {
                    required property int index
                    readonly property int day: index - root.firstDay + 1
                    readonly property bool valid: day > 0 && day <= root.days
                    readonly property bool isToday: root.offset === 0 && day === root.today.getDate()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 8
                    color: isToday ? root.theme.accent : "transparent"
                    Text { anchors.centerIn: parent; text: parent.valid ? parent.day : ""; color: parent.isToday ? root.theme.bg : root.theme.fg; font.family: "Inter"; font.pixelSize: 11; font.weight: parent.isToday ? Font.Bold : Font.Normal }
                }
            }
        }
        Text { text: root.offset === 0 ? Qt.formatDateTime(root.today, "dddd, d MMMM") : "Return to today"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10; TapHandler { onTapped: root.offset = 0 } }
    }
}
