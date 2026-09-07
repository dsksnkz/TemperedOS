//@ pragma ShellId tempered-boot

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: shell
    property real phase: 0
    property color backdrop: "#121923"
    property color accent: "#7ebeff"

    NumberAnimation on phase {
        from: 0; to: 1; duration: 3400; running: true
        easing.type: Easing.Linear
    }
    Timer { interval: 3500; running: true; onTriggered: Qt.quit() }

    Process {
        command: ["sh", "-lc", "cat ~/.config/tempered/palette.json"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const colors = JSON.parse(text)
                    shell.backdrop = colors.background || shell.backdrop
                    shell.accent = colors.accent || shell.accent
                } catch (error) {}
            }
        }
    }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: window
            required property var modelData
            screen: modelData
            color: "transparent"
            exclusiveZone: -1
            aboveWindows: true
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "tempered-boot"
            anchors { top: true; right: true; bottom: true; left: true }
            readonly property real handoffOpacity: shell.phase < 0.86 ? 1 : Math.max(0, 1 - (shell.phase - 0.86) / 0.14)

            Rectangle {
                anchors.fill: parent
                color: shell.backdrop
                opacity: window.handoffOpacity
            }

            Item {
                id: drop
                anchors.centerIn: parent
                width: Math.min(window.width, window.height) * 0.17
                height: width * 1.22
                opacity: window.handoffOpacity
                scale: shell.phase < 0.55
                     ? 0.72 + 0.28 * Math.sin(shell.phase / 0.55 * Math.PI / 2)
                     : 1 + Math.pow((shell.phase - 0.55) / 0.45, 3) * 34
                rotation: shell.phase < 0.55 ? -3 + shell.phase * 5 : -0.25

                Canvas {
                    id: canvas
                    anchors.fill: parent
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        const w = width, h = height
                        const gradient = ctx.createLinearGradient(w * 0.18, h * 0.05, w * 0.82, h)
                        gradient.addColorStop(0, Qt.lighter(shell.accent, 1.34))
                        gradient.addColorStop(0.58, shell.accent)
                        gradient.addColorStop(1, Qt.darker(shell.accent, 1.45))
                        ctx.fillStyle = gradient
                        ctx.beginPath()
                        ctx.moveTo(w * 0.50, h * 0.02)
                        ctx.bezierCurveTo(w * 0.47, h * 0.20, w * 0.10, h * 0.48, w * 0.10, h * 0.70)
                        ctx.bezierCurveTo(w * 0.10, h * 0.92, w * 0.28, h * 0.99, w * 0.50, h * 0.99)
                        ctx.bezierCurveTo(w * 0.72, h * 0.99, w * 0.90, h * 0.92, w * 0.90, h * 0.70)
                        ctx.bezierCurveTo(w * 0.90, h * 0.48, w * 0.53, h * 0.20, w * 0.50, h * 0.02)
                        ctx.closePath()
                        ctx.fill()

                        ctx.fillStyle = "rgba(255,255,255,0.36)"
                        ctx.beginPath()
                        ctx.ellipse(w * 0.34, h * 0.62, w * 0.075, h * 0.16, -0.45, 0, Math.PI * 2)
                        ctx.fill()
                    }
                    Connections {
                        target: shell
                        function onAccentChanged() { canvas.requestPaint() }
                    }
                }

                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: parent.height * 0.99
                    width: parent.width * (0.52 + 0.08 * Math.sin(shell.phase * 18))
                    height: 5
                    radius: 3
                    color: shell.accent
                    opacity: shell.phase < 0.52 ? 0.18 : 0
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 58
                text: "TEMPERED"
                color: Qt.rgba(1, 1, 1, shell.phase < 0.56 ? 0.56 : 0)
                font.family: "Inter"
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 4
            }
        }
    }
}
