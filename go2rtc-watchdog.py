#!/usr/bin/env python3
"""Watchdog that monitors Frigate logs and restarts go2rtc when recordings lose video.

After a camera reboot, Frigate's recordings sometimes get stuck as audio-only (~1/10 restarts).
The condition never self-recovers. This watchdog detects "icvExtractPattern" in Frigate logs
(meaning a recorded segment has no video track) and immediately restarts go2rtc to fix it.
"""

import logging
import os
import re
import subprocess
import time
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

FRIGATE_CONTAINER = os.environ.get("FRIGATE_CONTAINER", "frigate")
GO2RTC_URL = os.environ.get("GO2RTC_URL", "http://frigate:1984")
COOLDOWN = int(os.environ.get("COOLDOWN", "300"))
LOG_PATTERN = os.environ.get("LOG_PATTERN", r"icvExtractPattern")


def restart_go2rtc():
    """Restart the go2rtc daemon via its API."""
    log.info("Restarting go2rtc daemon...")
    url = f"{GO2RTC_URL}/api/restart"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
        log.info("go2rtc restart triggered successfully")
        return True
    except Exception as e:
        log.error("go2rtc restart failed: %s", e)
        return False


def main():
    pattern = re.compile(LOG_PATTERN)
    log.info("Watchdog starting")
    log.info("  Container: %s", FRIGATE_CONTAINER)
    log.info("  go2rtc API: %s", GO2RTC_URL)
    log.info("  Cooldown: %ds", COOLDOWN)
    log.info("  Trigger pattern: %s", LOG_PATTERN)

    last_restart = 0

    while True:
        cmd = ["docker", "logs", "-f", "--since", "5s", FRIGATE_CONTAINER]
        log.info("Tailing logs: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        try:
            for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if pattern.search(line):
                    now = time.time()
                    if now - last_restart < COOLDOWN:
                        log.info("Pattern matched but in cooldown, ignoring: %s", line)
                        continue
                    log.info("Pattern matched: %s", line)
                    restart_go2rtc()
                    last_restart = time.time()
        except Exception as e:
            log.error("Log follower error: %s", e)
        finally:
            proc.terminate()
            proc.wait()

        log.info("Log process exited, retrying in 5s...")
        time.sleep(5)


if __name__ == "__main__":
    main()
