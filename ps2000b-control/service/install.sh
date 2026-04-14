#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="ps2000b-control"
UNIT_FILE="$SCRIPT_DIR/$SERVICE_NAME.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (use sudo)." >&2
    exit 1
fi

if [ ! -f "$UNIT_FILE" ]; then
    echo "Error: $UNIT_FILE not found." >&2
    exit 1
fi

echo "Installing $SERVICE_NAME service..."
cp "$UNIT_FILE" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Done. Useful commands:"
echo "  sudo systemctl status  $SERVICE_NAME"
echo "  sudo systemctl stop    $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
