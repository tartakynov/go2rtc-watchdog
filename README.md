# go2rtc-watchdog

Temporary workaround for a bug where Frigate's recording permanently breaks after a camera restart. Probably only needed for Frigate < 0.17 — Frigate 0.17 introduced a built-in watchdog that detects segments without video and restarts the stream.

## Setup

```
Camera (Reolink) → Scrypted (RTSP rebroadcast) → go2rtc → Frigate recording
```

Scrypted rebroadcasts camera streams as RTSP so that multiple consumers (HomeKit, Frigate) can share a single camera connection. Frigate's go2rtc pulls from Scrypted's RTSP URLs and re-serves them locally for Frigate's recording and live view.

## The problem

After a camera reboot, Frigate's recordings sometimes get stuck without video (~1 in 10 restarts). Frigate silently stops recording video and only records audio. Live view continues to work. The condition never self-recovers — go2rtc must be restarted.

Scrypted is sending video to go2rtc — this is proven by live view working fine (new connections to go2rtc get video). The issue is in go2rtc/Frigate: after the upstream reconnects, old persistent connections (Frigate's recording FFmpeg) sometimes get stuck in a state where they can no longer decode the video packets.

## What the watchdog does

Monitors Frigate container logs for `icvExtractPattern` — an OpenCV error indicating it can't parse metadata from a recording segment. This can happen for other reasons, but in my case it means the saved segments have no video track. When the pattern is seen multiple times within a short window (default: 3 times in 60s), restarts go2rtc via `POST /api/restart` to force all connections to reinitialize. A cooldown prevents repeated restarts.

## Configuration

All via environment variables:

| Variable | Default | Description |
|---|---|---|
| `FRIGATE_CONTAINER` | `frigate` | Name of the Frigate Docker container to tail logs from |
| `GO2RTC_URL` | `http://frigate:1984` | go2rtc API base URL |
| `COOLDOWN` | `300` | Seconds to wait after a restart before allowing another |
| `LOG_PATTERN` | `icvExtractPattern` | Log pattern indicating recordings have no video |
| `TRIGGER_COUNT` | `3` | Number of pattern matches required to trigger a restart |
| `TRIGGER_WINDOW` | `60` | Time window in seconds for counting pattern matches |

## Requirements

- Docker socket access (reads sibling container logs via `docker logs -f`)
- Network access to Frigate's go2rtc API (port 1984)

## Usage

Add to your `docker-compose.yml`

```yaml
  go2rtc-watchdog:
    build: ./go2rtc-watchdog
    container_name: go2rtc-watchdog
    restart: unless-stopped
    environment:
      - FRIGATE_CONTAINER=frigate
      - GO2RTC_URL=http://frigate:1984
      - COOLDOWN=300
      - LOG_PATTERN=icvExtractPattern
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    depends_on:
      - frigate
    networks:
      frigate-internal:
```

Rebuild after changes

```
docker compose build --no-cache go2rtc-watchdog
docker compose up -d go2rtc-watchdog
```

