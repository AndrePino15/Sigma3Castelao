# Audio RTP/Opus Streaming

## Quick start

This receiver expects RTP audio over UDP using Opus with:

- payload type `96`
- `encoding-name=OPUS`
- `clock-rate=48000`
- UDP port from `SC_AUDIO_RTP_PORT` (default `5004`)

The audio worker runs in auto mode (`--mode stream`): it prefers the RTP stream and automatically falls back to silence when the stream is not available.

## Receiver (Pi / section-controller)

Run from the `source/` directory on the Pi:

```bash
export SC_AUDIO_RTP_PORT=5004
export SC_AUDIO_CODEC=opus
python -m audio.runner --mode stream
```

Optional: increase jitter tolerance if the network is unstable:

```bash
export SC_AUDIO_LATENCY_MS=150
python -m audio.runner --mode stream
```

## Sender (Laptop / server)

Replace `<PI_IP>` with the Raspberry Pi IP address on the same hotspot/Wi-Fi network.

### A) Send a test tone (sine) as RTP/Opus

```bash
gst-launch-1.0 -q \
  audiotestsrc wave=sine is-live=true ! \
  audioconvert ! audioresample ! \
  opusenc ! rtpopuspay pt=96 ! \
  udpsink host=<PI_IP> port=5004
```

### B) Send an audio file (WAV/MP3/etc.) as RTP/Opus

```bash
gst-launch-1.0 -q \
  filesrc location=/path/to/audio-file.mp3 ! \
  decodebin ! \
  audioconvert ! audioresample ! \
  opusenc ! rtpopuspay pt=96 ! \
  udpsink host=<PI_IP> port=5004
```

Looping is optional. Keep the sender simple first, then add looping later if needed.

## Networking notes

- UDP has no session reconnect. In practice, the receiver keeps listening/retrying, and the sender can be stopped/restarted at any time.
- Make sure the laptop and Pi are on the same hotspot/network.
- Always send to the Pi IP address (not `localhost` unless the sender runs on the Pi itself).

## Troubleshooting

- Check GStreamer is installed: `gst-launch-1.0 --version`
- Verify the sender UDP port matches `SC_AUDIO_RTP_PORT` on the receiver (default `5004`)
- If audio drops or is choppy, try increasing receiver latency: `SC_AUDIO_LATENCY_MS=150` (or higher)
- Confirm the laptop firewall is not blocking outbound/UDP traffic (and local policy is not blocking the sender)
