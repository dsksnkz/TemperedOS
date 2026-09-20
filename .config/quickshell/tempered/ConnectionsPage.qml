import QtQuick
import QtQuick.Layouts
import Quickshell.Networking
import Quickshell.Bluetooth

ColumnLayout {
    id: root
    required property var theme
    property bool wifi: true
    property var passwordNetwork: null
    readonly property var wifiDevice: {
        for (const device of Networking.devices.values)
            if (device.type === DeviceType.Wifi) return device
        return null
    }
    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property bool enabledRadio: wifi ? Networking.wifiEnabled : !!adapter?.enabled
    spacing: 10
    onVisibleChanged: {
        if (!visible) {
            if (wifiDevice) wifiDevice.scannerEnabled = false
            if (adapter) adapter.discovering = false
            passwordNetwork = null; password.text = ""
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Text { text: root.wifi ? "Wi-Fi" : "Bluetooth"; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
        Pill { theme: root.theme; text: "Scan"; enabled: root.enabledRadio; onTriggered: { if (root.wifi && root.wifiDevice) root.wifiDevice.scannerEnabled = true; else if (root.adapter) root.adapter.discovering = !root.adapter.discovering } }
        Pill { theme: root.theme; text: root.enabledRadio ? "On" : "Off"; selected: root.enabledRadio; onTriggered: { if (root.wifi) Networking.wifiEnabled = !Networking.wifiEnabled; else if (root.adapter) root.adapter.enabled = !root.adapter.enabled } }
    }
    ListView {
        id: devices
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true; spacing: 5
        model: root.wifi ? (root.wifiDevice?.networks ?? null) : (root.adapter?.devices ?? null)
        delegate: Rectangle {
            id: deviceRow
            required property var modelData
            width: devices.width; height: 48; radius: 14
            color: modelData.connected ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, .16) : hover.hovered ? Qt.rgba(root.theme.fg.r, root.theme.fg.g, root.theme.fg.b, .06) : "transparent"
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 12
                Text { text: root.wifi ? "󰖩" : "󰂯"; color: deviceRow.modelData.connected ? root.theme.accent : root.theme.fg; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 18 }
                Text { text: deviceRow.modelData.name || deviceRow.modelData.deviceName || "Device"; Layout.fillWidth: true; elide: Text.ElideRight; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 12 }
                Text { text: deviceRow.modelData.connected ? "Connected" : root.wifi ? Math.round(deviceRow.modelData.signalStrength * 100) + "%" : deviceRow.modelData.paired ? "Paired" : "Nearby"; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10 }
            }
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler {
                onTapped: {
                    if (deviceRow.modelData.connected) deviceRow.modelData.disconnect()
                    else if (!root.wifi) { if (deviceRow.modelData.paired) deviceRow.modelData.connect(); else deviceRow.modelData.pair() }
                    else if (deviceRow.modelData.known || deviceRow.modelData.security === WifiSecurityType.Open) deviceRow.modelData.connect()
                    else { root.passwordNetwork = deviceRow.modelData; password.forceActiveFocus() }
                }
            }
        }
        Text { anchors.centerIn: parent; visible: devices.count === 0; text: !root.enabledRadio ? "Turn on " + (root.wifi ? "Wi-Fi" : "Bluetooth") + " to see your devices." : "Nothing nearby yet. Try scanning."; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 12 }
    }
    Surface {
        visible: root.passwordNetwork !== null
        theme: root.theme; Layout.fillWidth: true; implicitHeight: 46
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 8
            TextInput {
                id: password
                Layout.fillWidth: true; color: root.theme.fg; font.family: "Inter"; font.pixelSize: 12; echoMode: TextInput.Password; clip: true
                function join() { if (root.passwordNetwork && text.length) root.passwordNetwork.connectWithPsk(text); text = ""; root.passwordNetwork = null }
                Keys.onReturnPressed: join()
                Text { visible: password.text.length === 0; text: "Password for " + (root.passwordNetwork?.name ?? "network"); color: root.theme.muted; font: password.font }
            }
            Pill { theme: root.theme; text: "Join"; compact: true; selected: true; onTriggered: password.join() }
        }
    }
    Text { text: root.wifi ? "Saved connections reconnect automatically." : "Select a device to pair or connect. PIN requests use your Bluetooth agent."; color: root.theme.muted; font.family: "Inter"; font.pixelSize: 10 }
}
