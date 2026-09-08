//@ pragma ShellId tempered-boot

import QtQuick
import Qt5Compat.GraphicalEffects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: shell
    property real phase: 0
    property color accent: "#7ebeff"
    property string wallpaper: Quickshell.env("HOME") + "/.config/tempered/wallpapers/default.png"

    function clamp(value) { return Math.max(0, Math.min(1, value)) }
    function outCubic(value) { const rest = 1 - clamp(value); return 1 - rest * rest * rest }
    function smooth(value) { value = clamp(value); return value * value * (3 - 2 * value) }

    NumberAnimation on phase { from: 0; to: 1; duration: 7000; running: true; easing.type: Easing.Linear }
    Timer { interval: 7000; running: true; onTriggered: Qt.quit() }

    Process {
        command: ["sh", "-lc", "cat \"$HOME/.config/tempered/palette.json\" 2>/dev/null"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const colors = JSON.parse(text)
                    shell.accent = colors.accent || shell.accent
                    shell.wallpaper = colors.wallpaper || shell.wallpaper
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
            color: "black"
            exclusiveZone: -1
            aboveWindows: true
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "tempered-boot"
            anchors { top: true; right: true; bottom: true; left: true }

            readonly property real fall: shell.outCubic(shell.phase / 0.25)
            readonly property real morph: shell.smooth((shell.phase - 0.25) / 0.09)
            readonly property real reveal: shell.smooth((shell.phase - 0.41) / 0.49)
            readonly property real startDiameter: 92
            readonly property real endDiameter: Math.sqrt(width * width + height * height) * 1.08

            Rectangle { anchors.fill: parent; color: "black" }

            Image {
                id: wallpaperSource
                anchors.fill: parent
                source: "file://" + shell.wallpaper
                fillMode: Image.PreserveAspectCrop
                asynchronous: false
                cache: false
                visible: false
            }

            Item {
                id: revealMask
                anchors.fill: parent
                visible: false
                Rectangle {
                    width: window.startDiameter + (window.endDiameter - window.startDiameter) * window.reveal
                    height: width
                    radius: width / 2
                    anchors.centerIn: parent
                    color: "white"
                }
            }

            OpacityMask {
                anchors.fill: parent
                source: wallpaperSource
                maskSource: revealMask
                opacity: window.reveal > 0 ? 1 : 0
                cached: false
            }

            Item {
                id: drop
                width: 92
                height: 112 - 20 * window.morph
                x: (window.width - width) / 2
                y: -height + ((window.height - height) / 2 + height) * window.fall
                opacity: 1 - shell.smooth((shell.phase - 0.405) / 0.035)

                Canvas {
                    id: dropCanvas
                    anchors.fill: parent
                    antialiasing: true
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        const w = width
                        const h = height
                        const m = window.morph
                        const top = 3
                        const sideY = h * (0.58 - 0.08 * m)
                        ctx.fillStyle = shell.accent
                        ctx.beginPath()
                        ctx.moveTo(w * 0.5, top)
                        ctx.bezierCurveTo(w * (0.50 - 0.28 * m), h * (0.20 - 0.18 * m), w * 0.08, h * (0.48 - 0.26 * m), w * 0.08, sideY)
                        ctx.bezierCurveTo(w * 0.08, h * 0.86, w * 0.28, h * 0.98, w * 0.5, h * 0.98)
                        ctx.bezierCurveTo(w * 0.72, h * 0.98, w * 0.92, h * 0.86, w * 0.92, sideY)
                        ctx.bezierCurveTo(w * 0.92, h * (0.48 - 0.26 * m), w * (0.50 + 0.28 * m), h * (0.20 - 0.18 * m), w * 0.5, top)
                        ctx.closePath()
                        ctx.fill()
                    }
                    Connections {
                        target: shell
                        function onPhaseChanged() { dropCanvas.requestPaint() }
                        function onAccentChanged() { dropCanvas.requestPaint() }
                    }
                }
            }

        }
    }
}
