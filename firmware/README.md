# 侦探相机固件

Open `PoetryCameraDirector/PoetryCameraDirector.ino` in Arduino IDE. The folder
retains its historical name to satisfy Arduino sketch naming requirements.
Install ESP32 Core 3.3.7 and ESP32-audioI2S 3.4.7 providing `Audio.h`.
The display uses the bundled driver. Wi-Fi and API secrets are not compiled in.
Select 16 MB Flash, OPI PSRAM (8 MB), USB CDC on boot, and the
`app3M_fat9M_16MB` partition scheme. Do not change partition layout on an
existing device without backing up its NVS and filesystem.

This sketch is the device side of the director-console workflow. It keeps Wi-Fi
and the backend URL on the ESP32, while all AI provider keys remain on the
server.

## First-time setup

1. Flash the sketch to the Waveshare ESP32-S3-CAM-OV5640.
2. Hold the board's `BOOT` button while restarting to force setup mode.
3. Join the `DASHAN-CAMERA-xxxx` Wi-Fi network with a phone.
4. Open `http://192.168.4.1`, select Wi-Fi, and enter the backend URL and device token.

If the saved Wi-Fi cannot be reached at startup, setup mode starts automatically.

## Implemented device contract

- `POST /api/device/heartbeat`
- `GET /api/device/jobs/next`
- `POST /api/device/jobs/{job_id}/complete`
- `POST /api/camera?job_id={job_id}` with a raw JPEG body

The camera pin map follows the supplied Waveshare board documentation. The
MY-628 uses UART0-compatible pins GPIO43 TX and GPIO44 RX at 9600 8N1.

## Fixed-layout printing

The server renders every ticket at exactly 384 dots using the bundled Zhuque
Fangsong and Courier Prime files. The ESP32 downloads the completed monochrome
job and sends it to MY-628 using the module vendor's documented `GS v 0`
horizontal raster command. UTF-8 text is never sent directly to the printer.
