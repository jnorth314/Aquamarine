import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import unittest

from device import Characteristic, CharacteristicState, Service, ServiceState, Device

class TestCharacteristic(unittest.TestCase):
    def test_create(self):
        characteristic = Characteristic("ABCD", 1, 2)

        self.assertEqual(characteristic.uuid, "ABCD")
        self.assertEqual(characteristic.handle, 1)
        self.assertEqual(characteristic.properties, 2)
        self.assertEqual(characteristic.state, CharacteristicState.NONE)

class TestService(unittest.TestCase):
    def test_create(self):
        service = Service("ABCD", 1)

        self.assertEqual(service.uuid, "ABCD")
        self.assertEqual(service.handle, 1)
        self.assertListEqual(service.characteristics, [])

    def test_get_characteristic_by_uuid(self):
        service = Service("ABCD", 1)
        characterstic = Characteristic("1234", 2, 2)

        service.characteristics.append(characterstic)

        self.assertEqual(service.get_characteristic_by_uuid("1234"), characterstic)
        self.assertIsNone(service.get_characteristic_by_uuid("5678"))

    def test_get_characteristic_by_handle(self):
        service = Service("ABCD", 1)
        characterstic = Characteristic("1234", 2, 2)

        service.characteristics.append(characterstic)

        self.assertEqual(service.get_characteristic_by_handle(2), characterstic)
        self.assertIsNone(service.get_characteristic_by_handle(3))

class TestDevice(unittest.TestCase):
    def test_create(self):
        device = Device("00:11:22:33:44:55")

        self.assertEqual(device.address, "00:11:22:33:44:55")
        self.assertIsNone(device.handle)
        self.assertEqual(device.packet, "")
        self.assertFalse(device.is_connectable)
        self.assertIsNone(device.address_type)
        self.assertIsNone(device.rssi)

        self.assertFalse(device.is_connected)
        self.assertListEqual(device.services, [])

    def test_on_advertisement(self):
        device = Device("00:11:22:33:44:55")

        device.on_advertisement("ABCD", 1, 1, -100)

        self.assertEqual(device.packet, "ABCD")
        self.assertTrue(device.is_connectable)
        self.assertEqual(device.address_type, 1)
        self.assertEqual(device.rssi, -100)

    def test_get_service_by_uuid(self):
        device = Device("00:11:22:33:44:55")
        service = Service("ABCD", 1)

        device.services.append(service)

        self.assertEqual(device.get_service_by_uuid("ABCD"), service)
        self.assertIsNone(device.get_service_by_uuid("1234"))

    def test_get_service_by_handle(self):
        device = Device("00:11:22:33:44:55")
        service = Service("ABCD", 1)

        device.services.append(service)

        self.assertEqual(device.get_service_by_handle(1), service)
        self.assertIsNone(device.get_service_by_handle(2))

    def test_get_characteristic_by_uuid(self):
        device = Device("00:11:22:33:44:55")
        service = Service("ABCD", 1)
        characterstic = Characteristic("1234", 2, 2)

        device.services.append(service)
        service.characteristics.append(characterstic)

        self.assertEqual(device.get_characteristic_by_uuid("1234"), characterstic)
        self.assertIsNone(device.get_characteristic_by_uuid("5678"))

    def test_get_characteristic_by_handle(self):
        device = Device("00:11:22:33:44:55")
        service = Service("ABCD", 1)
        characterstic = Characteristic("1234", 2, 2)

        device.services.append(service)
        service.characteristics.append(characterstic)

        self.assertEqual(device.get_characteristic_by_handle(2), characterstic)
        self.assertIsNone(device.get_characteristic_by_handle(3))

    def test_is_using_gatt_command(self):
        device = Device("00:11:22:33:44:55")
        service = Service("ABCD", 1)
        characterstic = Characteristic("1234", 2, 2)

        device.services.append(service)
        service.characteristics.append(characterstic)

        self.assertTrue(device.is_using_gatt_command())

        service.state = ServiceState.DISCOVERED
        self.assertFalse(device.is_using_gatt_command())

        characterstic.state = CharacteristicState.WRITING
        self.assertTrue(device.is_using_gatt_command())

if __name__ == "__main__":
    unittest.main()
