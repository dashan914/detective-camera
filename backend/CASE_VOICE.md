# Case narration candidate — 2026-09-16

This adds narration without replacing the 12 preset voices in `/voice/`.

## Flow

Photo -> detective result -> existing print job. A separate worker sends only
the subject, setup and conclusion to Fish Audio (`s2.1-pro-free`, 64 kbps MP3).
It never sends the photograph, device token or AI provider credentials.
There is no paid-model fallback and no automatic TTS retry.

An authenticated `case_audio` job becomes eligible after its print job reports
completed and the device advertises top-level `narration: "mp3-v1"`.
The device downloads at most 1 MiB into a separate temporary FFat file, waits
for the current preset voice to finish, then plays the case. The application
partition alone is updated; no filesystem or NVS image is flashed.

TTS failure does not block printing. Undelivered audio expires after 10 minutes.
Files are retained only for audio jobs in the bounded 100-job history.
ESP32 print completion means raster data was sent, not physical paper sensing.
Audio completion means the decoder stopped after playback, not microphone-based
confirmation that the speaker was audible.

## Configuration and testing

Server-only `.env`: `FISH_VOICE_ENABLED=1`, `FISH_API_KEY`, `FISH_REFERENCE_ID`.
Configure these values on the deployment host and protect `.env` with mode
0600. Never put keys or personal voice reference IDs in firmware or Git.

`POST /api/admin/narration/test` (admin authenticated) synthesizes the latest
completed printed detective case without taking another photo or printing again.
It rejects an active narration to avoid accidental duplicate requests.

`GET /api/device/jobs/{id}/audio-data` requires the existing device token.

Tests: `python3 -m unittest test_case_voice test_detective test_detective_renderer test_server`.

## Recovery

Back up your own application before changing firmware. Disable narration by
setting `FISH_VOICE_ENABLED=0` and restarting only your camera service.
Do not erase flash or overwrite the FFat/NVS partitions during recovery.
