# Shutter standby

PB0 on MCP23017 at 0x27 remains the physical shutter. A debounced release
under two seconds takes a photo. A two-second hold queues standby or wake.
A dedicated task samples the button every 5ms with 20ms debounce, independent
of camera preview and network requests; loop() consumes queued actions.
MCP transactions and display-expander writes share an I2C mutex. A held button
at boot must be released before use.

Standby is software idle, not power-off or ESP32 deep sleep. It blanks the
panel, disables backlight/amplifier while preserving EXIO5 BAT_EN, stops audio,
deinitializes camera capture and turns Wi-Fi off. Wake restarts the ESP32.
Presses during active cases, printing or audio are rejected, not deferred.

USB maintenance commands: S enters standby; R wakes while in standby.
Serial verification passed for enter/wake, camera init 0x0 and preview without
errors. Physical button verification is still required after the sampling fix.

Application-only rollback image is build-standby/before-standby-app.bin,
read from flash address 0x10000 before the initial standby update. Preserve
NVS, partition table and FFat when updating the application.
