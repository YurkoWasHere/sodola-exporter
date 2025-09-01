#!/bin/bash
# Sodola Exporter Installation Script

set -e

# Configuration
INSTALL_DIR="/opt/sodola-exporter"
SERVICE_USER="prometheus"
SERVICE_GROUP="prometheus"
SERVICE_FILE="sodola-exporter.service"
LOG_DIR="/var/log/sodola-exporter"

echo "Installing Sodola Exporter..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Create service user if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating user $SERVICE_USER..."
    useradd --system --shell /bin/false --home-dir /nonexistent --no-create-home $SERVICE_USER
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying exporter files..."
cp sodola_exporter.py "$INSTALL_DIR/"
cp sodola_http_exporter.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Make scripts executable
chmod +x "$INSTALL_DIR/sodola_exporter.py"
chmod +x "$INSTALL_DIR/sodola_http_exporter.py"

# Install Python dependencies
echo "Installing Python dependencies..."
cd "$INSTALL_DIR"
python3 -m pip install -r requirements.txt

# Create log directory
echo "Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"
chown "$SERVICE_USER:$SERVICE_GROUP" "$LOG_DIR"

# Set ownership
echo "Setting ownership..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"

# Install systemd service
echo "Installing systemd service..."
cp "$SERVICE_FILE" /etc/systemd/system/
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting service..."
systemctl enable sodola-exporter.service
systemctl start sodola-exporter.service

# Check service status
echo "Checking service status..."
systemctl status sodola-exporter.service --no-pager -l

# Test the service
echo "Testing HTTP endpoint..."
sleep 5
if curl -f http://localhost:9118/health > /dev/null 2>&1; then
    echo "✅ Service is running and responding"
    echo ""
    echo "Installation complete!"
    echo "Service endpoint: http://localhost:9118"
    echo "Health check: http://localhost:9118/health"
    echo "Example metrics: http://localhost:9118/sodola?target=192.168.40.6"
    echo ""
    echo "To view logs: journalctl -u sodola-exporter.service -f"
    echo "To stop service: systemctl stop sodola-exporter.service"
    echo "To restart service: systemctl restart sodola-exporter.service"
else
    echo "❌ Service may not be responding correctly"
    echo "Check logs: journalctl -u sodola-exporter.service"
    exit 1
fi