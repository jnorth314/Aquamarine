import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import unittest
from unittest.mock import Mock, patch

from device import Characteristic, CharacteristicState, Device, Service, ServiceState
from scanner import ScannerApp

class TestScannerApp(unittest.TestCase):
    @patch("serial.tools.list_ports.comports", return_value=[])
    def test_create_without_kit(self, _):
        self.assertRaises(ValueError, ScannerApp)

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_create_with_kit(self, *_):
        app = ScannerApp()

        self.assertListEqual(app.devices, [])
        self.assertFalse(app.is_running.is_set())
        self.assertFalse(app.is_ready.is_set())

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_stop(self, *_):
        app = ScannerApp()

        app.is_running.set()
        app.stop()
        self.assertFalse(app.is_running.is_set())

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_reboot(self, mock_lib, *_):
        app = ScannerApp()

        app.reboot()
        mock_lib.return_value.bt.system.reboot.assert_called_once()

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_on_advertisement(self, *_):
        app = ScannerApp()

        event = Mock()
        event.address = "00:11:22:33:44:55"
        event.data = b"\x12\x34"
        event.event_flags = 1
        event.address_type = 1
        event.rssi = -100

        app.on_advertisement(event)
        self.assertEqual(len(app.devices), 1)

        app.on_advertisement(event) # Duplicate event does NOT create a new device
        self.assertEqual(len(app.devices), 1)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_on_boot(self, mock_lib, *_):
        app = ScannerApp()

        app.on_boot()
        self.assertTrue(app.is_ready.is_set())
        mock_lib.return_value.bt.scanner.start.assert_called_once_with(
            mock_lib.return_value.bt.scanner.SCAN_PHY_SCAN_PHY_1M_AND_CODED,
            mock_lib.return_value.bt.scanner.DISCOVER_MODE_DISCOVER_GENERIC,
        )

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_on_connection_opened(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        app.devices.append(device)

        event = Mock()
        event.address = "00:11:22:33:44:55"
        event.connection = 1

        app.on_connection_opened(event)
        self.assertTrue(device.is_connected)
        mock_lib.return_value.bt.gatt.discover_primary_services.assert_called_once_with(1)

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_on_connection_closed(self, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        device.handle = 1
        device.is_connected = True

        app.devices.append(device)

        event = Mock()
        event.connection = 1

        app.on_connection_closed(event)
        self.assertFalse(device.is_connected)
        self.assertIsNone(device.handle)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_on_characteristic_value(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)
        characteristic = Characteristic("0001", 2, 0x20)

        device.handle = 1
        device.services.append(service)
        service.characteristics.append(characteristic)

        app.devices.append(device)

        event = Mock()
        event.att_opcode = mock_lib.return_value.bt.gatt.ATT_OPCODE_HANDLE_VALUE_INDICATION
        event.connection = 1
        event.characteristic = 2
        event.value = b"\x12\x34"

        app.on_characteristic_value(event)
        mock_lib.return_value.bt.gatt.send_characteristic_confirmation.assert_called_once_with(1)
        self.assertEqual(characteristic.packet, "1234")

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_on_service(self, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        device.handle = 1

        app.devices.append(device)

        event = Mock()
        event.connection = 1
        event.uuid = b"\xCD\xAB"
        event.service = 1

        app.on_service(event)
        self.assertEqual(len(device.services), 1)
        self.assertEqual(device.services[0].uuid, "ABCD")
        self.assertEqual(device.services[0].handle, 1)

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_on_characteristic(self, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)

        device.handle = 1
        device.services.append(service)

        app.devices.append(device)

        event = Mock()
        event.connection = 1
        event.uuid = b"\xCD\xAB"
        event.characteristic = 2
        event.properties = 0x02

        app.on_characteristic(event)
        self.assertEqual(len(service.characteristics), 1)
        self.assertEqual(service.characteristics[0].uuid, "ABCD")
        self.assertEqual(service.characteristics[0].handle, 2)
        self.assertEqual(service.characteristics[0].properties, 0x02)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_on_procedure_completed(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service1 = Service("0000", 1)
        service2 = Service("0001", 2)

        device.handle = 1
        device.services.append(service1)
        device.services.append(service2)

        app.devices.append(device)

        event = Mock()
        event.connection = 1

        app.on_procedure_completed(event)
        self.assertEqual(service1.state, ServiceState.DISCOVERED)
        self.assertEqual(service2.state, ServiceState.DISCOVERING)
        mock_lib.return_value.bt.gatt.discover_characteristics.assert_called_once_with(1, 2)

        app.on_procedure_completed(event)
        self.assertEqual(service2.state, ServiceState.DISCOVERED)

        characteristic = Characteristic("ABCD", 3, 0x02)
        characteristic.state = CharacteristicState.READING
        service1.characteristics.append(characteristic)
        app.on_procedure_completed(event)
        self.assertEqual(characteristic.state, CharacteristicState.NONE)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_connect_device(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        app.devices.append(device)

        device.handle = 1
        device.is_connected = False
        app.connect_device(device)
        mock_lib.return_value.bt.connection.open.assert_not_called()

        device.handle = None
        device.is_connected = False
        device.address_type = 1
        app.connect_device(device)
        mock_lib.return_value.bt.connection.open.assert_called_once_with(
            "00:11:22:33:44:55",
            1,
            mock_lib.return_value.bt.gap.PHY_PHY_1M
        )

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_disconnect_device(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        device.handle = 1

        app.devices.append(device)

        app.disconnect_device(device)
        mock_lib.return_value.bt.connection.close.assert_called_once_with(1)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_read_from_characteristic(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)
        service.state = ServiceState.DISCOVERED
        characteristic = Characteristic("0001", 2, 0x02)

        device.is_connected = True
        device.handle = 1
        device.services.append(service)
        service.characteristics.append(characteristic)

        app.devices.append(device)

        app.read_from_characteristic(device, characteristic)
        mock_lib.return_value.bt.gatt.read_characteristic_value.assert_called_once_with(1, 2)
        self.assertEqual(characteristic.state, CharacteristicState.READING)

        app.read_from_characteristic(device, characteristic)
        mock_lib.return_value.bt.gatt.read_characteristic_value.assert_called_once_with(1, 2)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_write_to_characteristic(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)
        service.state = ServiceState.DISCOVERED
        characteristic = Characteristic("0001", 2, 0x08)

        device.is_connected = True
        device.handle = 1
        device.services.append(service)
        service.characteristics.append(characteristic)

        app.devices.append(device)

        app.write_to_characteristic(device, characteristic, "ABCD")
        mock_lib.return_value.bt.gatt.write_characteristic_value.assert_called_once_with(1, 2, b"\xAB\xCD")
        self.assertEqual(characteristic.state, CharacteristicState.WRITING)

        app.write_to_characteristic(device, characteristic, "ABCD")
        mock_lib.return_value.bt.gatt.write_characteristic_value.assert_called_once_with(1, 2, b"\xAB\xCD")

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_subscribe_to_notification(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)
        service.state = ServiceState.DISCOVERED
        characteristic = Characteristic("0001", 2, 0x10)

        device.is_connected = True
        device.handle = 1
        device.services.append(service)
        service.characteristics.append(characteristic)

        app.devices.append(device)

        app.subscribe_to_notification(device, characteristic)
        mock_lib.return_value.bt.gatt.set_characteristic_notification.assert_called_once_with(1, 2, 1)
        self.assertEqual(characteristic.state, CharacteristicState.SUBSCRIBING_NOTIFICATION)

        app.subscribe_to_notification(device, characteristic)
        mock_lib.return_value.bt.gatt.set_characteristic_notification.assert_called_once_with(1, 2, 1)

    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    @patch("bgapi.BGLib")
    def test_subscribe_to_indication(self, mock_lib, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        service = Service("0000", 1)
        service.state = ServiceState.DISCOVERED
        characteristic = Characteristic("0001", 2, 0x10)

        device.is_connected = True
        device.handle = 1
        device.services.append(service)
        service.characteristics.append(characteristic)

        app.devices.append(device)

        app.subscribe_to_indication(device, characteristic)
        mock_lib.return_value.bt.gatt.set_characteristic_notification.assert_called_once_with(1, 2, 2)
        self.assertEqual(characteristic.state, CharacteristicState.SUBSCRIBING_INDICATION)

        app.subscribe_to_indication(device, characteristic)
        mock_lib.return_value.bt.gatt.set_characteristic_notification.assert_called_once_with(1, 2, 2)

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_get_device_by_address(self, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")

        app.devices.append(device)

        self.assertEqual(app.get_device_by_address("00:11:22:33:44:55"), device)
        self.assertIsNone(app.get_device_by_address("66:77:88:99:AA:BB"))

    @patch("bgapi.BGLib")
    @patch("bgapi.SerialConnector")
    @patch("serial.tools.list_ports.comports", return_value=[("COM1", "JLink CDC UART", None)])
    def test_get_device_by_handle(self, *_):
        app = ScannerApp()
        device = Device("00:11:22:33:44:55")
        device.handle = 1

        app.devices.append(device)

        self.assertEqual(app.get_device_by_handle(1), device)
        self.assertIsNone(app.get_device_by_handle(2))

if __name__ == "__main__":
    unittest.main()
