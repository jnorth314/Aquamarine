import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import random

from PyQt6.QtWidgets import QApplication
from unittest.mock import patch

from device import Characteristic, Device, Service
from scanner import ScannerWidget

NUM_DEVICES = 50
NUM_SERVICES_PER_DEVICE = 15
NUM_CHARACTERISTICS_PER_SERVICE = 10

def create_devices() -> list[Device]:
    """Create a list of fake Devices/Services/Characteristics"""

    devices = [Device(":".join(f"{random.randrange(256):02X}" for _ in range(6))) for _ in range(NUM_DEVICES)]

    for device in devices:
        device.rssi = random.randrange(-120, -20)
        device.is_connectable = random.choice([True, False])

        if device.is_connectable:
            device.is_connected = random.choice([True, False])

        if device.is_connected:
            device.services = [
                Service(
                    random.choice([f"{random.randrange(2**16):04X}", f"{random.randrange(2**128):016X}"]),
                    random.randrange(2**32)
                ) for _ in range(NUM_SERVICES_PER_DEVICE)
            ]

            for service in device.services:
                service.characteristics = [
                    Characteristic(
                        random.choice([f"{random.randrange(2**16):04X}", f"{random.randrange(2**128):016X}"]),
                        random.randrange(2**32),
                        random.randrange(8) << 3 | random.randrange(1) << 1
                    ) for _ in range(NUM_CHARACTERISTICS_PER_SERVICE)
                ]
        elif device.is_connectable:
            device.handle = random.choice([None, 1])

    return devices

def main() -> None:
    """Create the fake GUI for quick widget graphical debugging"""

    app = QApplication(sys.argv)

    with (
        patch("bgapi.BGLib"),
        patch("bgapi.SerialConnector"),
        patch("scanner.ScannerApp.run"),
        patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    ):
        window = ScannerWidget()
        window.app.devices = create_devices()
        window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
