from enum import IntEnum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

class CharacteristicState(IntEnum):
    """enum for handling whether a characteristic is currently being used for a gatt command"""

    NONE = 0
    READING = 1
    WRITING = 2
    SUBSCRIBING_NOTIFICATION = 3
    SUBSCRIBING_INDICATION = 4

class Characteristic: # pylint: disable=too-few-public-methods
    """Class for holding information pertaining to a Bluetooth characteristic"""

    def __init__(self, uuid: str, handle: int, properties: int) -> None:
        self.uuid = uuid
        self.handle = handle
        self.properties = properties

        self.state = CharacteristicState.NONE
        self.packet = ""

class ServiceState(IntEnum):
    """enum for the current discovery state of a Service"""

    DISCOVERING = 1
    DISCOVERED = 2

class Service:
    """Class for holding information pertaining to a Bluetooth service"""

    def __init__(self, uuid: str, handle: int) -> None:
        self.uuid = uuid
        self.handle = handle

        self.state = ServiceState.DISCOVERING
        self.characteristics: list[Characteristic] = []

    def get_characteristic_by_uuid(self, uuid: str) -> Characteristic | None:
        """Get the corresponding characteristic with the matching UUID"""

        for characteristic in self.characteristics:
            if characteristic.uuid == uuid:
                return characteristic

        return None

    def get_characteristic_by_handle(self, handle: int) -> Characteristic | None:
        """Get the corresponding characteristic with the matching handle"""

        for characteristic in self.characteristics:
            if characteristic.handle == handle:
                return characteristic

        return None

class Device: # pylint: disable=too-many-instance-attributes
    """Class for holding information pertaining to a Bluetooth device"""

    def __init__(self, address: str) -> None:
        self.address = address
        self.handle: int | None = None

        self.packet = ""
        self.is_connectable = False
        self.address_type: int | None = None
        self.rssi: int | None = None

        self.is_connected = False
        self.services: list[Service] = []

    def on_advertisement(self, packet: str, event_flags: int, address_type: int, rssi: int) -> None:
        """Callback for when the device sends an advertisment packet"""

        self.packet = packet
        self.is_connectable = event_flags & 1 != 0
        self.address_type = address_type
        self.rssi = rssi

    def get_service_by_uuid(self, uuid: str) -> Service | None:
        """Get the corresponding service with the matching UUID"""

        for service in self.services:
            if service.uuid == uuid:
                return service

        return None

    def get_service_by_handle(self, handle: int) -> Service | None:
        """Get the corresponding service with the matching handle"""

        for service in self.services:
            if service.handle == handle:
                return service

        return None

    def get_characteristic_by_uuid(self, uuid: str) -> Characteristic | None:
        """Get the corresponding characteristic with the matching UUID"""

        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid == uuid:
                    return characteristic

        return None

    def get_characteristic_by_handle(self, handle: int) -> Characteristic | None:
        """Get the corresponding characteristic with the matching handle"""

        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.handle == handle:
                    return characteristic

        return None

    def is_using_gatt_command(self) -> bool:
        """Check whether a characteristic in the device is currently being read/written/subscribed to"""

        return (
            any(service.state != ServiceState.DISCOVERED for service in self.services) or
            any(characteristic.state != CharacteristicState.NONE
                for service in self.services
                for characteristic in service.characteristics)
        )

class CharacteristicWidget(QFrame): # pragma: no cover, pylint: disable=too-many-instance-attributes
    """Widget for displaying Characteristic information in a GUI"""

    def __init__(self, device: Device, characteristic: Characteristic) -> None:
        super().__init__()

        self.device = device
        self.characteristic = characteristic

        self.uuid = QLabel()
        self.handle = QLabel()

        self.read_button = QPushButton()
        self.write_button = QPushButton()
        self.notify_button = QPushButton()
        self.indicate_button = QPushButton()

        self.packet = QLabel()

        self.uuid.setText(self.characteristic.uuid)
        self.uuid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.handle.setText(f"[{self.characteristic.handle:08X}]")
        self.handle.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.read_button.setEnabled(self.characteristic.properties & 0x02 != 0)
        self.read_button.setFixedSize(32, 32)

        self.write_button.setEnabled(self.characteristic.properties & 0x08 != 0)
        self.write_button.setFixedSize(32, 32)

        self.notify_button.setEnabled(self.characteristic.properties & 0x10 != 0)
        self.notify_button.setFixedSize(32, 32)

        self.indicate_button.setEnabled(self.characteristic.properties & 0x20 != 0)
        self.indicate_button.setFixedSize(32, 32)

        self.packet.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        row1 = QHBoxLayout()
        row1.addWidget(self.uuid)
        row1.addWidget(self.handle)

        row2 = QHBoxLayout()
        row2.addWidget(self.read_button)
        row2.addWidget(self.write_button)
        row2.addWidget(self.notify_button)
        row2.addWidget(self.indicate_button)

        row3 = QHBoxLayout()
        row3.addWidget(self.packet)

        column = QVBoxLayout()
        column.addLayout(row1)
        column.addLayout(row2)
        column.addLayout(row3)

        self.setLayout(column)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)

        self.update_layout()

    def update_layout(self) -> None:
        """Update the layout with the information from the Characteristic class"""

        self.read_button.setText("R")
        self.write_button.setText("W")
        self.notify_button.setText("N")
        self.indicate_button.setText("I")

        match self.characteristic.state:
            case CharacteristicState.READING:
                self.read_button.setText("R...")
            case CharacteristicState.WRITING:
                self.write_button.setText("W...")
            case CharacteristicState.SUBSCRIBING_NOTIFICATION:
                self.notify_button.setText("N...")
            case CharacteristicState.SUBSCRIBING_INDICATION:
                self.indicate_button.setText("I...")

        self.packet.setText(self.characteristic.packet)

        self.update()

class ServiceWidget(QFrame): # pragma: no cover
    """Widget for displaying Service information in a GUI"""

    def __init__(self, device: Device, service: Service) -> None:
        super().__init__()

        self.device = device
        self.service = service

        self.uuid = QLabel()
        self.handle = QLabel()

        self.uuid.setText(self.service.uuid)
        self.uuid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.handle.setText(f"[{self.service.handle:08X}]")
        self.handle.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row = QHBoxLayout()
        row.addWidget(self.uuid)
        row.addWidget(self.handle)

        self.setLayout(row)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)

class DeviceWidget(QFrame): # pragma: no cover
    """Widget for displaying Device information in a GUI"""

    def __init__(self, device: Device) -> None:
        super().__init__()

        self.device = device

        self.rssi = QLabel()
        self.address = QLabel()
        self.button = QPushButton()

        self.rssi.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.rssi.setFixedSize(56, 16)

        self.address.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.address.setText(self.device.address)
        self.address.setFixedSize(112, 16)

        self.button.setFixedSize(84, 24)

        row = QHBoxLayout()
        row.addWidget(self.rssi)
        row.addWidget(self.address)
        row.addWidget(self.button)

        self.setLayout(row)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)

        self.update_layout()

    def update_layout(self) -> None:
        """Update the layout with the information from the Device class"""

        self.rssi.setText(f"{self.device.rssi} dBm" if self.device.rssi is not None else "N/A")

        if self.device.is_connected:
            self.button.setText("Disconnect")
        elif self.device.handle is not None:
            self.button.setText("Connecting...")
        else:
            self.button.setText("Connect")

        self.button.setEnabled(self.device.is_connectable)

        self.update()
