import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Mpris

RowLayout {
    id: root
    required property var theme
    readonly property var player: theme.player
    property real position: 0
    spacing: 20
    function timecode(value) { return Math.floor(value / 60) + ":" + Math.floor(value % 60).toString().padStart(2, "0") }
    Timer { interval: 500; running: root.visible && !!root.player; repeat: true; triggeredOnStart: true; onTriggered: root.position = root.player.position }
    Surface {
        theme: root.theme
        Layout.preferredWidth: 284
        Layout.fillHeight: true
        clip: true
        Image { id: artwork; anchors.fill: parent; anchors.margins: 12; source: root.player?.trackArtUrl ?? ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 512; sourceSize.height: 512; visible: status === Image.Ready }
        Column {
            anchors.centerIn: parent; visible: artwork.status !== Image.Ready; spacing: 12
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "󰝚"; color: root.theme.accent; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 70 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "ROOM FOR SOUND"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9; font.letterSpacing: 2 }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { text: root.player?.identity ?? "YOUR MUSIC"; color: root.theme.accent; font.family: "Inter"; font.pixelSize: 10; font.letterSpacing: 1; Layout.fillWidth: true }
            Pill { theme: root.theme; glyph: "↗"; compact: true; visible: !!root.player?.canRaise; onTriggered: { root.player.raise(); root.theme.sheetOpen = false } }
        }
        Item { Layout.fillHeight: true }
        Text { Layout.fillWidth: true; text: root.player?.trackTitle || "Set the tone"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 25; font.weight: Font.DemiBold; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight }
        Text { Layout.fillWidth: true; text: root.player?.trackArtist || (root.player ? root.player.trackAlbum : "Play music in any MPRIS-enabled app."); color: root.theme.muted; font.family: "Inter"; font.pixelSize: 13; elide: Text.ElideRight }
        FluidSlider { Layout.fillWidth: true; visible: !!root.player?.lengthSupported; enabled: !!root.player?.canSeek; modelValue: root.position / Math.max(1, root.player?.length ?? 1); foreground: root.theme.fg; accent: root.theme.accent; motionScale: root.theme.motionScale; onCommitted: value => { if (root.player?.canSeek) root.player.position = value * root.player.length } }
        RowLayout {
            visible: !!root.player?.lengthSupported; Layout.fillWidth: true; Layout.topMargin: -12
            Text { text: root.timecode(root.position); color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9; Layout.fillWidth: true }
            Text { text: root.timecode(root.player?.length ?? 0); color: root.theme.muted; font.family: "Inter"; font.pixelSize: 9 }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Pill { theme: root.theme; glyph: "󰒮"; enabled: !!root.player?.canGoPrevious; onTriggered: root.player.previous() }
            Pill { theme: root.theme; glyph: root.player?.isPlaying ? "󰏤" : "󰐊"; text: root.player?.isPlaying ? "Pause" : "Play"; selected: true; enabled: !!root.player?.canTogglePlaying; onTriggered: root.player.togglePlaying() }
            Pill { theme: root.theme; glyph: "󰒭"; enabled: !!root.player?.canGoNext; onTriggered: root.player.next() }
            Item { Layout.fillWidth: true }
            Pill { theme: root.theme; glyph: "󰒟"; selected: !!root.player?.shuffle; enabled: !!root.player?.shuffleSupported; onTriggered: root.player.shuffle = !root.player.shuffle }
        }
        Item { Layout.fillHeight: true }
        RowLayout {
            spacing: 6
            Repeater {
                model: Mpris.players
                Pill { required property var modelData; theme: root.theme; text: modelData.identity; compact: true; selected: root.player === modelData; onTriggered: root.theme.preferredPlayer = modelData }
            }
        }
    }
}
