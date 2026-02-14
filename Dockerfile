FROM python:3.12-alpine

# Docker CLI needed to tail sibling container logs
RUN apk add --no-cache docker-cli

COPY go2rtc-watchdog.py /go2rtc-watchdog.py
ENTRYPOINT ["python3", "-u", "/go2rtc-watchdog.py"]
