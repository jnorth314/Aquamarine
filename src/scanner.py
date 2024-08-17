import os
import threading
import typing

import bgapi
from PyQt6.QtCore import Qt, QRegularExpression, QTimer
from PyQt6.QtGui import QCloseEvent, QFont, QIcon, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QWidget, QVBoxLayout
)
import serial.tools.list_ports

from device import (
    Characteristic, CharacteristicState, CharacteristicWidget, Device, DeviceWidget, Service, ServiceState,
    ServiceWidget
)

MAX_RETRY_ATTEMPTS = 3

class ScannerApp(threading.Thread):
    """Thread for handling event callbacks on the BGM220 Explorer Kit"""

    def __init__(self) -> None:
        super().__init__(daemon=True)

        @typing.no_type_check
        def get_port_of_module() -> str:
            """Grab the serial port of the BGM220 Explorer Kit"""

            for port, desc, _ in serial.tools.list_ports.comports():
                if "JLink CDC UART" in desc:
                    return port

            raise ValueError("BGM220 Explorer Kit not detected!")

        port = get_port_of_module()
        path_to_api = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../res/sl_bt.xapi")

        self.devices: list[Device] = []

        self.lib = bgapi.BGLib(bgapi.SerialConnector(port, rtscts=True), path_to_api)
        self.is_running = threading.Event()
        self.is_ready = threading.Event()

    def run(self) -> None: # pragma: no cover
        """Thread for handling events of the BGM220"""

        self.lib.open()
        self.is_running.set()
        threading.Thread(target=self.watchdog, daemon=True).start()

        while self.is_running.is_set():
            try:
                # In order to allow for keyboard interrupts when running without the GUI a timeout is included
                event = self.lib.get_event(timeout=0.1)

                if event is None:
                    continue

                # For easier debugging, advertisements can clutter the console
                if not event == "bt_evt_scanner_legacy_advertisement_report":
                    print(event)

                # We do not want to handle events until after the system is ready, however in order to be ready the boot
                # event does need to get handled.
                if not (self.is_ready.is_set() or event == "bt_evt_system_boot"):
                    continue

                match event:
                    case "bt_evt_scanner_legacy_advertisement_report":
                        self.on_advertisement(event)
                    case "bt_evt_system_boot":
                        self.on_boot()
                    case "bt_evt_connection_opened":
                        self.on_connection_opened(event)
                    case "bt_evt_connection_closed":
                        self.on_connection_closed(event)
                    case "bt_evt_gatt_service":
                        self.on_service(event)
                    case "bt_evt_gatt_characteristic":
                        self.on_characteristic(event)
                    case "bt_evt_gatt_characteristic_value":
                        self.on_characteristic_value(event)
                    case "bt_evt_gatt_procedure_completed":
                        self.on_procedure_completed(event)
            except KeyboardInterrupt:
                self.is_running.clear()

        self.lib.close()

    def stop(self) -> None:
        """Terminate the main loop"""

        self.is_running.clear()

    def watchdog(self) -> None: # pragma: no cover
        """Task for waiting for the BGM220 Explorer Kit to reboot"""

        if self.is_ready.wait(1):
            return

        retry = 0

        while retry < MAX_RETRY_ATTEMPTS:
            self.reboot()
            retry += 1

            if self.is_ready.wait(10):
                return

        self.stop()

    def reboot(self) -> None:
        """Reboot the BGM220 Explorer Kit and setup for scanning"""

        self.lib.bt.system.reboot()

    def on_advertisement(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives an advertisement"""

        address = event.address.upper()

        packet = event.data.hex().upper()
        event_flags = event.event_flags
        address_type = event.address_type
        rssi = event.rssi

        device = self.get_device_by_address(address)

        if device is None:
            self.devices.append(device := Device(address))

        device.on_advertisement(packet, event_flags, address_type, rssi)

    def on_boot(self) -> None:
        """Callback for when the BGM220 Explorer Kit boots"""

        self.is_ready.set()
        self.lib.bt.scanner.start(
            self.lib.bt.scanner.SCAN_PHY_SCAN_PHY_1M_AND_CODED,
            self.lib.bt.scanner.DISCOVER_MODE_DISCOVER_GENERIC
        )

    def on_connection_opened(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a connection opened event"""

        device = self.get_device_by_address(event.address.upper())

        if device is not None:
            device.is_connected = True
            self.lib.bt.gatt.discover_primary_services(event.connection)

    def on_connection_closed(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a connection closed event"""

        device = self.get_device_by_handle(event.connection)

        if device is not None:
            device.is_connected = False
            device.handle = None

    def on_characteristic_value(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a characteristic value event"""

        if event.att_opcode == self.lib.bt.gatt.ATT_OPCODE_HANDLE_VALUE_INDICATION:
            self.lib.bt.gatt.send_characteristic_confirmation(event.connection)

        device = self.get_device_by_handle(event.connection)

        if device is not None:
            characteristic = device.get_characteristic_by_handle(event.characteristic)

            if characteristic is not None:
                characteristic.packet = event.value.hex()

    def on_service(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a discovered service event"""

        device = self.get_device_by_handle(event.connection)

        if device is not None:
            uuid = event.uuid[::-1].hex().upper()
            device.services.append(Service(uuid, event.service))

    def on_characteristic(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a discovered characteristic event"""

        device = self.get_device_by_handle(event.connection)

        if device is not None:
            uuid = event.uuid[::-1].hex().upper()

            for service in device.services:
                if service.state == ServiceState.DISCOVERING:
                    service.characteristics.append(Characteristic(uuid, event.characteristic, event.properties))
                    return

    def on_procedure_completed(self, event: bgapi.bglib.BGEvent) -> None:
        """Callback for when the BGM220 Explorer Kit receives a procedure completed event"""

        def update_services_and_characteristics(device: Device) -> None:
            """Update the state for the currently active service or characteristic"""

            for service in device.services:
                if service.state != ServiceState.DISCOVERED:
                    service.state = ServiceState.DISCOVERED
                    return

                for characteristic in service.characteristics:
                    if characteristic.state != CharacteristicState.NONE:
                        characteristic.state = CharacteristicState.NONE
                        return

        device = self.get_device_by_handle(event.connection)

        if device is not None:
            update_services_and_characteristics(device)

            for service in device.services:
                if service.state == ServiceState.DISCOVERING:
                    self.lib.bt.gatt.discover_characteristics(device.handle, service.handle)
                    break

    def connect_device(self, device: Device) -> None:
        """Connect the device to the BGM220 Explorer Kit"""

        # A device has already been assigned a handle and is attempting to connect
        if any(device.handle is not None and not device.is_connected for device in self.devices):
            return

        response = self.lib.bt.connection.open(device.address, device.address_type, self.lib.bt.gap.PHY_PHY_1M)
        device.handle = response.connection

        #TODO: Set a timer to check if the device has connected, otherwise the kit will be stuck attempting

    def disconnect_device(self, device: Device) -> None:
        """Disconnect the device from the BGM220 Explorer Kit"""

        if device.handle is not None:
            self.lib.bt.connection.close(device.handle)

    def read_from_characteristic(self, device: Device, characteristic: Characteristic) -> None:
        """Read from a device connected to the BGM220 Explorer Kit"""

        if device.is_using_gatt_command():
            return

        if device.is_connected:
            self.lib.bt.gatt.read_characteristic_value(device.handle, characteristic.handle)
            characteristic.state = CharacteristicState.READING

    def write_to_characteristic(self, device: Device, characteristic: Characteristic, packet: str) -> None:
        """Write to a device connected to the BGM220 Explorer Kit"""

        if device.is_using_gatt_command():
            return

        if device.is_connected:
            self.lib.bt.gatt.write_characteristic_value(device.handle, characteristic.handle, bytes.fromhex(packet))
            characteristic.state = CharacteristicState.WRITING
            characteristic.packet = packet

    def subscribe_to_notification(self, device: Device, characteristic: Characteristic) -> None:
        """Subscribe to a device's notification connected to the BGM220 Explorer Kit"""

        if device.is_using_gatt_command():
            return

        if device.is_connected:
            self.lib.bt.gatt.set_characteristic_notification(device.handle, characteristic.handle, 1)
            characteristic.state = CharacteristicState.SUBSCRIBING_NOTIFICATION

    def subscribe_to_indication(self, device: Device, characteristic: Characteristic) -> None:
        """Subscribe to a device's indication connected to the BGM220 Explorer Kit"""

        if device.is_using_gatt_command():
            return

        if device.is_connected:
            self.lib.bt.gatt.set_characteristic_notification(device.handle, characteristic.handle, 2)
            characteristic.state = CharacteristicState.SUBSCRIBING_INDICATION

    def get_device_by_address(self, address: str) -> Device | None:
        """Get the corresponding device with the matching address"""

        for device in self.devices:
            if device.address == address:
                return device

        return None

    def get_device_by_handle(self, handle: int) -> Device | None:
        """Get the corresponding device with the matching handle"""

        for device in self.devices:
            if device.handle == handle:
                return device

        return None

class HeaderWidget(QWidget): # pragma: no cover
    """Widget for a header on top of list widgets for navigation"""

    def __init__(self) -> None:
        super().__init__()

        self.button = QPushButton()
        self.label = QLabel()

        font = QFont()
        font.setPixelSize(24)

        self.button.setText("<")
        self.button.setFixedSize(32, 32)
        self.button.hide()

        self.label.setFont(font)
        self.label.setText("Devices")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        row = QHBoxLayout()
        row.addWidget(self.button)
        row.addWidget(self.label)

        self.setLayout(row)

class WriteDialog(QDialog): # pragma: no cover
    """Widget for handling creating hex packets for writing to characteristics"""

    def __init__(self) -> None:
        super().__init__()

        self.has_accepted = False
        self.packet = ""

        self.label = QLabel()
        self.edit = QLineEdit()
        self.accept_button = QPushButton()

        self.label.setText("HEX:")
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.edit.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]+")))

        self.accept_button.setText("Accept")
        self.accept_button.clicked.connect(self.on_accept)

        row = QHBoxLayout()
        row.addWidget(self.label)
        row.addWidget(self.edit)
        row.addWidget(self.accept_button)

        self.setLayout(row)
        self.setWindowTitle("Write Characteristic")
        self.setFixedWidth(320)

    def on_accept(self) -> None:
        """Callback for when the accept button is pushed"""

        self.has_accepted = True
        self.packet = self.edit.text().upper()

        if len(self.packet)%2 != 0:
            self.packet = "0" + self.packet

        self.close()

class ScannerWidget(QWidget): # pragma: no cover
    """GUI for handling communication between devices and BGM220 Explorer Kit"""

    def __init__(self) -> None:
        super().__init__()

        self.app = ScannerApp()
        self.app.start()

        self.setWindowTitle("Aquamarine")
        self.setFixedSize(360, 480)

        path_to_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../res/icon.ico")
        self.setWindowIcon(QIcon(path_to_icon))

        self.header = HeaderWidget()
        self.devices = QListWidget()
        self.services = QListWidget()
        self.characteristics = QListWidget()

        self.header.button.clicked.connect(self.on_back_button)
        self.devices.itemClicked.connect(self.on_selection)
        self.services.itemClicked.connect(self.on_selection)

        self.services.hide()
        self.characteristics.hide()

        column = QVBoxLayout()
        column.addWidget(self.header)
        column.addWidget(self.devices)
        column.addWidget(self.services)
        column.addWidget(self.characteristics)
        self.setLayout(column)

        # Create a timer for active rendering of the GUI - no need to be fast
        timer = QTimer(self)
        timer.timeout.connect(self.update_layout)
        timer.start(100)

    @typing.no_type_check
    def update_layout(self) -> None:
        """Update the GUI based on data from the ScannerApp"""

        # Update all of the existing widgets in the lists
        for i in range(self.devices.count()):
            self.devices.itemWidget(self.devices.item(i)).update_layout()

        for i in range(self.characteristics.count()):
            self.characteristics.itemWidget(self.characteristics.item(i)).update_layout()

        # Add remaining missing device widgets to the list
        devices = [self.devices.itemWidget(self.devices.item(i)).device for i in range(self.devices.count())]
        for device in self.app.devices:
            if device not in devices:
                item = QListWidgetItem()
                widget = DeviceWidget(device)

                widget.button.clicked.connect(self.on_connect_button)

                item.setSizeHint(widget.minimumSizeHint())

                self.devices.addItem(item)
                self.devices.setItemWidget(item, widget)

        # Add services based on the currently selected device
        services = [self.services.itemWidget(self.services.item(i)).service for i in range(self.services.count())]
        device_widget = self.devices.itemWidget(self.devices.currentItem())
        if device_widget is not None:
            device = device_widget.device

            for service in device.services:
                if service not in services:
                    item = QListWidgetItem()
                    widget = ServiceWidget(device, service)

                    item.setSizeHint(widget.minimumSizeHint())

                    self.services.addItem(item)
                    self.services.setItemWidget(item, widget)

        # Add characteristics based on the currently selected service
        characteristics = [self.characteristics.itemWidget(self.characteristics.item(i)).characteristic
                           for i in range(self.characteristics.count())]
        service_widget = self.services.itemWidget(self.services.currentItem())
        if service_widget is not None:
            service = service_widget.service

            for characteristic in service.characteristics:
                if characteristic not in characteristics:
                    item = QListWidgetItem()
                    widget = CharacteristicWidget(device, characteristic)

                    widget.read_button.clicked.connect(self.on_read_button)
                    widget.write_button.clicked.connect(self.on_write_button)
                    widget.notify_button.clicked.connect(self.on_notify_button)
                    widget.indicate_button.clicked.connect(self.on_indicate_button)

                    item.setSizeHint(widget.minimumSizeHint())

                    self.characteristics.addItem(item)
                    self.characteristics.setItemWidget(item, widget)

    @typing.no_type_check
    def on_selection(self, item: QListWidgetItem) -> None:
        """Callback when a selection is made to change view from devices or services"""

        match self.sender():
            case self.devices:
                if self.devices.itemWidget(item).device.is_connected:
                    self.devices.hide()
                    self.services.show()
                    self.header.label.setText("Services")
                    self.header.button.show()
            case self.services:
                self.services.hide()
                self.characteristics.show()
                self.header.label.setText("Characteristics")
                self.header.button.show()
            case _:
                pass

    @typing.no_type_check
    def on_back_button(self) -> None:
        """Callback for when the back button is hit"""

        if self.services.isVisible():
            self.services.hide()
            self.devices.show()
            self.header.button.hide()
            self.header.label.setText("Devices")
            return

        if self.characteristics.isVisible():
            self.characteristics.hide()
            self.services.show()
            self.header.button.show()
            self.header.label.setText("Services")
            return

    @typing.no_type_check
    def on_connect_button(self) -> None:
        """Callback for when a DeviceWidget's connect button is clicked"""

        device = self.sender().parent().device

        if device.is_connected:
            self.app.disconnect_device(device)
        else:
            self.app.connect_device(device)

    @typing.no_type_check
    def on_read_button(self) -> None:
        """Callback for when a CharacteristicWidget's read button is clicked"""

        widget = self.sender().parent()

        device = widget.device
        characteristic = widget.characteristic

        self.app.read_from_characteristic(device, characteristic)

    @typing.no_type_check
    def on_write_button(self) -> None:
        """Callback for when a CharacteristicWidget's write button is clicked"""

        dialog = WriteDialog()
        dialog.exec()

        if dialog.has_accepted:
            widget = self.sender().parent()

            device = widget.device
            characteristic = widget.characteristic

            self.app.write_to_characteristic(device, characteristic, dialog.packet)

    @typing.no_type_check
    def on_notify_button(self) -> None:
        """Callback for when a CharacteristicWidget's notify button is clicked"""

        widget = self.sender().parent()

        device = widget.device
        characteristic = widget.characteristic

        self.app.subscribe_to_notification(device, characteristic)

    @typing.no_type_check
    def on_indicate_button(self) -> None:
        """Callback for when a CharacteristicWidget's indicate button is clicked"""

        widget = self.sender().parent()

        device = widget.device
        characteristic = widget.characteristic

        self.app.subscribe_to_indication(device, characteristic)

    def closeEvent(self, event: QCloseEvent | None) -> None: # pylint: disable=invalid-name
        """Event when the user closes the window"""

        if event is not None:
            self.app.stop()
            self.app.join()
            event.accept()
