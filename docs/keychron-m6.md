# Keychron M6 8K over the 2.4 GHz receiver

Battery Notifier reads the battery level of the Keychron M6 8K through its receiver, Keychron Ultra-Link 8K (`3434:D028`), with the stock firmware.
The protocol is the one used by [Keychron Launcher](https://launcher.keychron.com).

Tested on Windows.

## Linux permissions

On Linux, the receiver's raw HID interface is only readable by root by default. Allow the logged-in user to access it with a udev rule, e.g. `/etc/udev/rules.d/70-keychron-ultra-link.rules`:

```
KERNEL=="hidraw*", ATTRS{idVendor}=="3434", ATTRS{idProduct}=="d028", TAG+="uaccess"
```

Then reload the rules and reconnect the receiver:

```sh
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Protocol

Battery Notifier talks to the receiver's vendor interface (usage page `0xFFC1`, usage `0x01`) with 64-byte reports, report ID included:

| Request     | Reply                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------- |
| `B3 06 00…` | `B4 06 …`, byte 20 is the battery: bits 0-6 are the percentage, bit 7 the charging state |

The receiver also sends unsolicited status reports starting with `E2`, they are skipped.
If the mouse does not answer within 1 second (asleep, off, or charging over the cable), the battery level shows as N/A.
