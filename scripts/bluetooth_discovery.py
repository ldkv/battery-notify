import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("battery_notifier")

# Standard Bluetooth GATT characteristics
BATTERY_SERVICE_UUID = "180F"  # Battery Service
BATTERY_CHAR_UUID = "2A19"  # Battery Level Characteristic
DEVICE_INFO_UUID = "180A"  # Device Information Service
MODEL_NUMBER_UUID = "2A24"  # Model Number Characteristic
MANUFACTURER_UUID = "2A29"  # Manufacturer Name Characteristic


@dataclass
class BluetoothDevice:
    name: str = "Unknown Bluetooth Device"
    address: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    battery_level: int = 0
    is_connected: bool = False
    services: dict = field(default_factory=dict)

    async def get_battery_level(self) -> bool:
        """Get battery level of a connected Bluetooth device."""
        try:
            async with BleakClient(self.address, timeout=5.0) as client:
                if not client.is_connected:
                    logger.info(f"Device {self.name} is not connected")
                    return False

                self.is_connected = True
                # Get services to check if battery service is available
                services = client.services
                has_battery = False
                for service in services:
                    if BATTERY_SERVICE_UUID.lower() in service.uuid.lower():
                        has_battery = True
                        break

                if not has_battery:
                    logger.info(f"Device {self.name} does not support battery service")
                    return False

                # Try to get device info
                try:
                    manufacturer = await client.read_gatt_char(MANUFACTURER_UUID)
                    self.manufacturer = manufacturer.decode()
                except Exception:
                    pass

                try:
                    model = await client.read_gatt_char(MODEL_NUMBER_UUID)
                    self.model = model.decode()
                except Exception:
                    pass

                # Try to get battery level
                try:
                    battery = await client.read_gatt_char(BATTERY_CHAR_UUID)
                    self.battery_level = int(battery[0])
                    logger.info(f"Device: {self.name} - Battery level: {self.battery_level}%")
                    return True
                except Exception as e:
                    logger.warning(f"Could not read battery level for {self.name}: {e}")
        except Exception as e:
            logger.error(f"Connection error for {self.name} ({self.address}): {e}")

        return False

    def __str__(self):
        name = self.name
        if self.manufacturer and self.model:
            name = f"{self.manufacturer} {self.model}"
        battery = f" (Battery: {self.battery_level}%)" if self.battery_level > 0 else ""
        return f"{name}{battery}"


def get_paired_devices() -> Dict[str, str]:
    """Get list of paired Bluetooth devices using system_profiler."""
    try:
        # Run system_profiler to get Bluetooth information in JSON format
        cmd = ["system_profiler", "SPBluetoothDataType", "-json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        data = json.loads(result.stdout)

        # Extract paired devices
        paired_devices = {}
        for controller in data.get("SPBluetoothDataType", []):
            devices = controller.get("device_connected", [])
            for device in devices:
                for name, device_info in device.items():
                    address = device_info.get("device_address")
                    if address:
                        paired_devices[address] = name
                    logger.info(f"Found paired device: {name} ({address})")

        return paired_devices
    except Exception as e:
        logger.error(f"Error getting paired devices: {e}")
        return {}


async def get_connected_devices() -> List[BluetoothDevice]:
    """Get battery levels for paired Bluetooth devices."""
    devices = []
    logger.info("Getting paired Bluetooth devices...")

    # Get list of paired devices
    paired_devices = get_paired_devices()
    if not paired_devices:
        logger.info("No paired devices found")
        return devices

    try:
        # Scan for devices
        discovered_devices = await BleakScanner.discover(
            # return_adv=True,
            # service_uuids=args.services,
            # cb={"use_bdaddr": True},
        )

        for device in discovered_devices:
            if device.address not in paired_devices:
                continue

            logger.info(f"Checking paired device: {device.name} ({device.address})")
            bluetooth_device = BluetoothDevice(name=paired_devices[device.address], address=device.address)
            if await bluetooth_device.get_battery_level():
                devices.append(bluetooth_device)

    except Exception as e:
        logger.error(f"Error during device discovery: {e}")

    return devices


async def main():
    address = "E2:F6:31:9D:E1:F5"
    # bluetooth_device = BluetoothDevice(name="Keychron K2 HE", address=address)
    # if await bluetooth_device.get_battery_level():
    #     print(bluetooth_device)
    devices = await get_connected_devices()

    if not devices:
        print("\nNo paired Bluetooth devices found with battery information")
        return

    print("\nPaired Bluetooth devices with battery levels:")
    for device in devices:
        print(f"- {device}")


if __name__ == "__main__":
    asyncio.run(main())
