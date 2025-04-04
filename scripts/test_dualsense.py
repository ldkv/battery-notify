import asyncio
import sys
from typing import Optional

from battery_notifier.devices.hid_wrapper import DeviceInfo, HIDWrapper
from battery_notifier.logs import logger

# DualSense controller vendor and product IDs
DUALSENSE_VID = 0x054C  # Sony
DUALSENSE_PID = 0x0CE6  # DualSense

async def find_dualsense() -> Optional[DeviceInfo]:
    """Find a connected DualSense controller."""
    devices = HIDWrapper.enumerate_matching_devices(DUALSENSE_VID, DUALSENSE_PID)
    if not devices:
        logger.error("No DualSense controller found")
        return None
    
    # Return the first found device
    return devices[0]

async def monitor_battery(device_info: DeviceInfo):
    """Monitor battery level of DualSense controller."""
    hid_device = HIDWrapper(device_info.path)
    if not hid_device:
        logger.error("Failed to open DualSense controller")
        return

    try:
        while True:
            # Get detailed battery info
            battery_level, is_charging, is_full = hid_device.get_dualsense_battery_info()
            
            if battery_level >= 0:
                status = []
                if is_charging:
                    status.append("Charging")
                if is_full:
                    status.append("Fully charged")
                
                status_str = f" ({', '.join(status)})" if status else ""
                print(f"\rBattery: {battery_level}%{status_str}", end="", flush=True)
            else:
                print("\rFailed to read battery level", end="", flush=True)
            
            # Wait 5 seconds before next check
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        print("\nStopping battery monitor...")
    finally:
        hid_device.close()

async def main():
    # Find DualSense controller
    device_info = await find_dualsense()
    if not device_info:
        return

    print(f"Found DualSense controller: {device_info}")
    print("Monitoring battery level (press Ctrl+C to stop)...")
    
    # Start battery monitoring
    await monitor_battery(device_info)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0) 