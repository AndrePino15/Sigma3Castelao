#!/usr/bin/env bash
set -e
echo "[+] Starting Mosquitto broker on localhost:1883 using Docker..."
docker run --rm -it -p 1883:1883 -p 9001:9001 eclipse-mosquitto:2
