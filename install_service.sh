#!/bin/bash
# Install astro_cat as a systemd service

set -e

SERVICE_FILE="astro_cat.service"
SERVICE_NAME="astro_cat"

echo "Installing Astro Cat systemd service..."
echo "========================================"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script needs sudo privileges to install the service."
    echo ""
    echo "Please run: sudo ./install_service.sh"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get the user who invoked sudo (the actual user, not root)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER="$(whoami)"
fi

echo "Installing for user: $ACTUAL_USER"
echo "Working directory: $SCRIPT_DIR"

# Check if service file exists
if [ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]; then
    echo "Error: $SERVICE_FILE not found in $SCRIPT_DIR"
    exit 1
fi

# Check if venv exists
if [ ! -f "$SCRIPT_DIR/venv/bin/python" ]; then
    echo "Error: Python virtual environment not found at $SCRIPT_DIR/venv"
    echo "Please run setup.sh first to create the virtual environment."
    exit 1
fi

# Copy service file to systemd directory with substitutions
echo "Copying service file to /etc/systemd/system/..."
sed -e "s|__USER__|$ACTUAL_USER|g" -e "s|__WORKDIR__|$SCRIPT_DIR|g" "$SCRIPT_DIR/$SERVICE_FILE" > /etc/systemd/system/$SERVICE_FILE

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service to start at boot
echo "Enabling service to start at boot..."
systemctl enable $SERVICE_NAME

# Start the service
echo "Starting service..."
systemctl start $SERVICE_NAME

# Check status
echo ""
echo "Service installation complete!"
echo ""
echo "Service status:"
systemctl status $SERVICE_NAME --no-pager

echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME    # Check status"
echo "  sudo systemctl stop $SERVICE_NAME      # Stop service"
echo "  sudo systemctl start $SERVICE_NAME     # Start service"
echo "  sudo systemctl restart $SERVICE_NAME   # Restart service"
echo "  sudo journalctl -u $SERVICE_NAME -f    # View logs"
echo ""
echo "The web interface should now be available at: http://localhost:8000"
