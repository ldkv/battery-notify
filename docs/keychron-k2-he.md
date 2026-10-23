# Keychron K2 HE over the 2.4 GHz receiver

With stock firmware, the K2 HE does not report its battery level through the Keychron Link receiver (`3434:D030`), on any OS.
Battery Notifier reads it with a small firmware change that makes the keyboard answer a battery request sent through the receiver.

In Bluetooth mode no custom firmware is needed: Windows reads the battery level natively, and Battery Notifier picks it up with the other Bluetooth devices.

## Firmware

The firmware is on [ldkv/qmk_firmware](https://github.com/ldkv/qmk_firmware), branch `2025q3` (merged in [ldkv/qmk_firmware#1](https://github.com/ldkv/qmk_firmware/pull/1)), a fork of [Keychron/qmk_firmware](https://github.com/Keychron/qmk_firmware):

- Adds the raw HID command `KC_GET_BATTERY` (`0xA4`), with the reply layout from [Keychron/qmk_firmware#477](https://github.com/Keychron/qmk_firmware/pull/477).
- Enables `WILRESS_RAW_ENABLE` on the K2 HE, so requests forwarded by the receiver reach the keyboard.
- Fixes the wireless raw HID handler, which called the removed `via_raw_hid_receive()`.

It is based on the published source, versioned 1.2.1: settings added in Keychron's 1.3.0 firmware (not published yet) are missing, and updating from Keychron Launcher removes the battery report.

Build it, e.g. for the ANSI layout with the QMK Docker image:

```sh
git clone --depth 1 --branch 2025q3 https://github.com/ldkv/qmk_firmware.git && cd qmk_firmware
git submodule update --init --depth 1 lib/chibios lib/chibios-contrib lib/printf
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/qmk_firmware -w /qmk_firmware ghcr.io/qmk/qmk_cli make keychron/k2_he/ansi:keychron
```

## Flashing

Flashing may reset the keyboard settings: export your Keychron Launcher profile first.

1. Disconnect the USB cable and set the mode switch to **Cable**.
2. Hold **Esc** (or the reset button under the space bar) while connecting the USB cable: the keyboard enters the STM32 bootloader.
3. Flash `keychron_k2_he_ansi_keychron.bin`:
   - Windows: [QMK Toolbox](https://github.com/qmk/qmk_toolbox/releases), select the file and click **Flash**.
   - macOS: `brew install dfu-util`, then `dfu-util -a 0 -d 0483:DF11 -s 0x08000000:leave -D keychron_k2_he_ansi_keychron.bin`

To go back to stock firmware, flash the official one from Keychron the same way.

## Protocol

Battery Notifier talks to the receiver's raw HID interface (usage page `0xFF60`, usage `0x61`) with 32-byte reports:

| Request | Reply                                                                                                             |
| ------- | ----------------------------------------------------------------------------------------------------------------- |
| `B2`    | Receiver state, answered by the receiver itself: `B2 xx` then slots of `VID (LE) PID (LE) connected`              |
| `A4`    | Battery, answered by the keyboard: `A4 percentage mV_low mV_high charging transport model_id` (K2 HE model ID: 3) |

If the receiver reports the keyboard as disconnected (asleep or off), or the keyboard does not answer `A4` within 1 second (stock firmware), the battery level shows as N/A.
