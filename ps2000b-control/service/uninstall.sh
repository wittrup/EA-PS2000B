#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="ps2000b-control"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (use sudo)." >&2
    exit 1
fi

echo "Removing $SERVICE_NAME service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload

echo "Done. Service removed."
