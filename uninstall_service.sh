#!/bin/bash
# Uninstall astro_cat systemd service

set -e

SERVICE_NAME="astro_cat"

echo "Uninstalling Astro Cat systemd service..."
echo "=========================================="

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges to uninstall the service."
    echo ""
    echo "Please run: sudo ./uninstall_service.sh"
    exit 1
fi

# Stop the service if running
echo "Stopping service..."
systemctl stop $SERVICE_NAME 2>/dev/null || true

# Disable the service
echo "Disabling service..."
systemctl disable $SERVICE_NAME 2>/dev/null || true

# Remove service file
echo "Removing service file..."
rm -f /etc/systemd/system/$SERVICE_NAME.service

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo ""
echo "Service uninstalled successfully!"
