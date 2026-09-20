import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: root
    required property var theme
    required property var desk
    required property date now
    spacing: 12

    Surface {
        theme: root.theme
        Layout.preferredWidth: 270
        Layout.fillWidth: true
        Layout.fillHeight: true
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 9
            RowLayout {
                Layout.fillWidth: true
                Text { text: "A little room to focus"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Text { text: (root.desk.state.today ?? 0) + " today"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9 }
            }
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Canvas {
                    id: dial
                    anchors.centerIn: parent
                    width: Math.min(parent.width, parent.height); height: width
                    property real progress: root.desk.progress
                    property color accent: root.theme.accent
                    onProgressChanged: requestPaint()
                    onAccentChanged: requestPaint()
                    onPaint: {
                        const c = getContext("2d"); c.reset()
                        const r = width / 2 - 9, center = width / 2
                        c.lineWidth = 2; c.strokeStyle = Qt.rgba(accent.r, accent.g, accent.b, 0.17)
                        c.beginPath(); c.arc(center, center, r, 0, 2 * Math.PI); c.stroke()
                        c.lineWidth = 3; c.lineCap = "round"; c.strokeStyle = accent
                        c.beginPath(); c.arc(center, center, r, -Math.PI / 2, -Math.PI / 2 + Math.max(.008, progress) * 2 * Math.PI); c.stroke()
                        for (let i = 0; i < 12; ++i) {
                            const angle = i * Math.PI / 6
                            c.fillStyle = Qt.rgba(accent.r, accent.g, accent.b, .4)
                            c.beginPath(); c.arc(center + (r-9)*Math.sin(angle), center - (r-9)*Math.cos(angle), 1, 0, 2*Math.PI); c.fill()
                        }
                    }
                }
                Column {
                    anchors.centerIn: parent; spacing: 5
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.desk.active ? root.desk.timeLeft : root.desk.state.focus?.state === "done" ? "Well done" : "25:00"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: root.desk.state.focus?.state === "done" ? 24 : 33; font.weight: Font.Light }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.desk.state.focus?.state === "paused" ? "PAUSED" : root.desk.active ? (root.desk.state.focus.kind === "break" ? "BREATHE" : "ONE THING AT A TIME") : "YOUR NEXT CHAPTER"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 8; font.letterSpacing: 1 }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                visible: !root.desk.active
                Pill { theme: root.theme; text: "25 min"; selected: true; enabled: root.desk.ready; onTriggered: root.desk.send("start", {minutes: 25}) }
                Pill { theme: root.theme; text: "50"; enabled: root.desk.ready; onTriggered: root.desk.send("start", {minutes: 50}) }
                Pill { theme: root.theme; text: "Break"; enabled: root.desk.ready; onTriggered: root.desk.send("start", {minutes: 5, kind: "break"}) }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                visible: root.desk.active
                Pill { theme: root.theme; text: root.desk.state.focus?.state === "paused" ? "Resume" : "Pause"; selected: true; onTriggered: root.desk.send(root.desk.state.focus.state === "paused" ? "resume" : "pause") }
                Pill { theme: root.theme; text: "Finish"; onTriggered: root.desk.send("reset") }
            }
        }
    }
    CalendarCard { theme: root.theme; today: root.now; Layout.preferredWidth: 280; Layout.fillWidth: true; Layout.fillHeight: true }
    Surface {
        theme: root.theme
        Layout.preferredWidth: 250
        Layout.fillWidth: true
        Layout.fillHeight: true
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 10
            RowLayout {
                Text { text: "Leave yourself a thought"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Text { text: "↗"; color: root.theme.accent; font.pixelSize: 16 }
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                TextArea {
                    id: note
                    enabled: root.desk.ready
                    color: root.theme.fg
                    placeholderText: "An idea. The next small step.\nSomething to come back to."
                    placeholderTextColor: root.theme.muted
                    font.family: "Inter"; font.pixelSize: 12
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    selectionColor: root.theme.accent
                    selectedTextColor: root.theme.bg
                    background: null
                    leftPadding: 0; rightPadding: 0
                    onTextChanged: if (activeFocus) saveNote.restart()
                    onActiveFocusChanged: if (!activeFocus && saveNote.running) saveNote.flush()
                    Component.onCompleted: text = root.desk.state.note ?? ""
                }
            }
            Text { text: root.desk.state.error || (!root.desk.ready ? "Desk storage unavailable" : saveNote.running ? "Saving…" : "Saved on this device · Only you"); Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.desk.state.error ? root.theme.accent2 : root.theme.muted; font.family: "Inter"; font.pixelSize: 9 }
            RowLayout {
                Pill { theme: root.theme; glyph: "󰸉"; text: "Wallpaper"; compact: true; onTriggered: root.theme.launch("~/.local/bin/tempered-wallpaper-picker") }
                Pill { theme: root.theme; glyph: "󰒓"; compact: true; onTriggered: root.theme.launch("~/.local/bin/tempered-settings") }
            }
        }
        Connections {
            target: root.desk
            function onStateChanged() { if (!note.activeFocus && !saveNote.running) note.text = root.desk.state.note ?? "" }
        }
        Timer {
            id: saveNote
            interval: 450
            function flush() { stop(); root.desk.send("note", {text: note.text}) }
            onTriggered: flush()
        }
        Connections { target: root.theme; function onSheetOpenChanged() { if (!root.theme.sheetOpen && saveNote.running) saveNote.flush() } }
    }
}
