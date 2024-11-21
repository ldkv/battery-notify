# Bluetooth scanner
# Prints the name and address of every nearby Bluetooth LE device

import asyncio

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData

adv: AdvertisementData = None

MODEL_NBR_UUID = "2A19"
uuid_battery_level_characteristic = "00002A19-0000-1000-8000-00805f9b34fb"


async def main():
    devices = await BleakScanner.discover(return_adv=True, timeout=30)
    for address, (_, adv) in devices.items():
        if "1000" not in str(adv.local_name):
            continue

        print(f"{address}: {adv}")
    # address = "66:EB:41:EE:D4:71"  # Bose 700
    # address = "E8:BC:51:D0:95:6E"  # Nuphy
    # address = "88:C9:E8:D6:69:AF"
    address = "C0:9A:01:76:D4:B2"  # Sony WH-1000XM4
    print(f"Connecting to {address}")
    #  Get-PnpDevice -FriendlyName "*nuphy*" | ForEach-Object {
    #     $local:test = $_ |
    #     Get-PnpDeviceProperty -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' |
    #         Where Type -ne Empty;
    #     if ($test) {
    #         "To query battery for $($_.FriendlyName), run the following:"
    #         "    Get-PnpDeviceProperty -InstanceId '$($test.InstanceId)' -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' | % Data"
    #         ""
    #         "The result will look like this:";
    #         Get-PnpDeviceProperty -InstanceId $($test.InstanceId) -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' | % Data
    #     }
    # }
    # this_device = await BleakScanner.find_device_by_address(address, timeout=20)
    async with BleakClient(address) as client:
        print(f"Connected: {address} / {client.is_connected}")
        for service in client.services:
            print(f"\t\tDescription: {service.description}")
            print(f"\t\tService: {service}")
            # battery_level = await client.read_gatt_char(uuid_battery_level_characteristic)
            # battery_level = int.from_bytes(battery_level)
            # print(f"{battery_level=}")

            print("\t\tCharacteristics:")
            for c in service.characteristics:
                print(f"\t\t\t{c}")
                try:
                    battery_level = await client.read_gatt_char(c.uuid)
                    # battery_level = int.from_bytes(battery_level)
                    print(f"{battery_level=} / {c.uuid}")
                except Exception as e:
                    print(f"Failed to connect to {address}: {e}")
        model_number = await client.read_gatt_char(uuid_battery_level_characteristic)
        battery_level = await client.read_gatt_char(uuid_battery_level_characteristic)
        battery_level = int.from_bytes(battery_level)
        print(f"{battery_level=}")
        for service in client.services:
            print(f"\t\tDescription: {service.description}")
            print(f"\t\tService: {service}")
            battery_level = await client.read_gatt_char(uuid_battery_level_characteristic)
            battery_level = int.from_bytes(battery_level)
            print(f"{battery_level=}")

        print("\t\tCharacteristics:")
        for c in service.characteristics:
            print(f"\t\t\t{c}")
        (print(f"\t\t\tUUID: {c.uuid}"),)
        print(f"\t\t\tDescription: {c.description}")
        (print(f"\t\t\tHandle: {c.handle}"),)
        print(f"\t\t\tProperties: {c.properties}")

        print("\t\tDescriptors:")
        for descrip in c.descriptors:
            print(f"\t\t\t{descrip}")
        print(f"{service}")
        for c in service.characteristics:
            print(f"{c}")
            try:
                battery_level = await client.read_gatt_char(c.handle)
                battery_level = int.from_bytes(battery_level)
                print(f"{battery_level=}")
            except Exception as e:
                print(f"Failed to connect to {address}: {e}")


def socket_test():
    import socket

    baddr = "E8:BC:51:D0:95:6E"
    channel = 3
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    for channel in range(31):
        try:
            s.connect((baddr, channel))
            break
        except Exception as e:
            print(f"Failed to connect to {baddr}: {e}")
    # s.connect((baddr, channel))
    s_sock = server_sock.accept()
    print("Accepted connection from " + address)

    data = s_sock.recv(1024)
    print("received [%s]" % data)

    s.listen(1)


# socket_test()
asyncio.run(main())
