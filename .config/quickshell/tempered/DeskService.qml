import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var state: ({note: "", focus: {}, remaining: 0, today: 0})
    readonly property bool ready: worker.running && received
    property bool received: false
    readonly property bool active: state.focus?.state === "running" || state.focus?.state === "paused"
    readonly property string timeLeft: Math.floor((state.remaining ?? 0) / 60).toString().padStart(2, "0") + ":" + ((state.remaining ?? 0) % 60).toString().padStart(2, "0")
    readonly property real progress: active ? 1 - (state.remaining ?? 0) / Math.max(1, state.focus?.total ?? 1500) : state.focus?.state === "done" ? 1 : 0

    function send(action, values) {
        if (ready) worker.write(JSON.stringify(Object.assign({action: action}, values || {})) + "\n")
    }
    Process {
        id: worker
        command: ["python3", "-u", Quickshell.shellPath("desk.py")]
        running: true
        stdinEnabled: true
        stdout: SplitParser {
            onRead: data => {
                try { root.state = JSON.parse(data); root.received = true }
                catch (error) { console.warn("Desk state:", error) }
            }
        }
    }
}
