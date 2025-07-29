#!/bin/bash
set -e

echo "🧹 Cleaning up GrowPro installation..."

# Stop and remove InfluxDB container
if docker ps -a --format '{{.Names}}' | grep -q influxdb2; then
    echo "🗑 Stopping and removing InfluxDB container..."
    docker stop influxdb2 || true
    docker rm influxdb2 || true
fi

# Remove Docker volumes and disable Docker
echo "🧼 Disabling Docker service..."
sudo systemctl disable --now docker || true
sudo apt purge -y docker.io docker-compose || true
sudo rm -rf /var/lib/docker /var/lib/containerd

# Stop and disable Node-RED
echo "🛑 Stopping Node-RED..."
sudo systemctl stop nodered || true
sudo systemctl disable nodered || true
rm -rf ~/.node-red

# Remove Mosquitto config and disable
echo "🔌 Removing Mosquitto..."
sudo systemctl stop mosquitto || true
sudo systemctl disable mosquitto || true
sudo apt purge -y mosquitto mosquitto-clients || true
sudo rm -rf /etc/mosquitto

# Remove Samba
echo "📂 Removing Samba..."
sudo systemctl stop smbd || true
sudo systemctl disable smbd || true
sudo apt purge -y samba samba-common-bin || true

# Remove GrowPro files
echo "🧽 Removing GrowPro files..."
rm -rf /home/pi/growpro
sudo rm -rf /etc/systemd/system/growpro*

# Remove Python virtual environment
echo "🐍 Removing Python virtual environment..."
rm -rf /home/pi/growpro/venv

# Optionally: reset hostname
echo "📛 Resetting hostname..."
sudo hostnamectl set-hostname raspberrypi
sudo sed -i 's/127.0.1.1.*/127.0.1.1\traspberrypi/' /etc/hosts

# Optionally: remove kernel panic auto-reboot config
sudo sed -i '/^kernel\.panic/d' /etc/sysctl.conf
sudo sysctl -p

echo "✅ Cleanup complete."
