#!/bin/bash
set -e  # Exit script on any error

cat /home/pi/growpro/assets/growpro-ascii.txt

echo "🚀 Starting GrowPro Setup..."


# --- [1] Update system and install packages ---
echo "📦 Updating system and installing packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    samba samba-common-bin \
    mosquitto mosquitto-clients \
    ffmpeg \
    python3-venv python3-full
    
echo "☑️  Done..."

# --- [2] Configure Samba ---
echo "🗂 Configuring Samba..."
# Add Samba password for user 'pi'
echo -e "growpro\ngrowpro" | sudo smbpasswd -a pi || true
# Ensure correct ownership
sudo chown -R pi:pi /home/pi/growpro
# Add Samba share for the entire growpro directory
if ! grep -q "^\[growpro\]" /etc/samba/smb.conf; then
    echo "📁 Adding Samba share for /home/pi/growpro..."
    echo -e "\n[growpro]
   path = /home/pi/growpro
   writeable = yes
   browseable = yes
   guest ok = no
   create mask = 0644
   directory mask = 0755
   force user = pi" | sudo tee -a /etc/samba/smb.conf > /dev/null
else
    echo "ℹ️ Samba share [growpro] already exists. Skipping."
fi
# Enable and restart Samba service
sudo systemctl enable smbd
sudo systemctl restart smbd


# --- [3] Install Node-RED and Node.js ---
echo "🧱 Installing Node-RED and Node.js..."
bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered) --no-init
# --- [4] Copy Node-RED configuration ---
echo "⚙️ Copying Node-RED configuration..."
sudo systemctl stop nodered
# Copy main config files
cp /home/pi/growpro/nodered/settings.js ~/.node-red/
cp /home/pi/growpro/nodered/flows*.json ~/.node-red/
cp /home/pi/growpro/nodered/package*.json ~/.node-red/
cp /home/pi/growpro/nodered/package-lock*.json ~/.node-red/
cd ~/.node-red
npm install
# --- [5] Start Node-RED ---
echo "🔁 Enabling and restarting Node-RED service..."
sudo systemctl enable nodered.service
sudo systemctl restart nodered.service


# --- [6] Install Docker ---
echo "🐳 Installing Docker..."
curl -sSL https://get.docker.com | sh
sudo usermod -aG docker pi
sudo systemctl enable --now docker


# --- [7] Start InfluxDB Docker container ---
echo "📦 Starting InfluxDB Docker container..."
sudo docker run -d \
  --name=influxdb2 \
  --restart unless-stopped \
  -p 8086:8086 \
  -v /home/pi/influxdb2:/var/lib/influxdb2 \
  -e DOCKER_INFLUXDB_INIT_MODE=setup \
  -e DOCKER_INFLUXDB_INIT_USERNAME=admin \
  -e DOCKER_INFLUXDB_INIT_PASSWORD=GrowPro123! \
  -e DOCKER_INFLUXDB_INIT_ORG=growpro \
  -e DOCKER_INFLUXDB_INIT_BUCKET=growpro_bucket \
  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=SuperToken123! \
  influxdb:2.7


# --- [8] Configure Mosquitto MQTT broker ---
echo "📡 Configuring Mosquitto..."
echo -e "listener 1883\nallow_anonymous true" | sudo tee /etc/mosquitto/mosquitto.conf > /dev/null
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto


# --- [9] Setup Python virtual environment and install dependencies ---
echo "🐍 Creating Python virtual environment..."
python3 -m venv /home/pi/growpro/venv
source /home/pi/growpro/venv/bin/activate
pip install --upgrade pip
pip install -r /home/pi/growpro/requirements.txt
deactivate


# --- [10] Enable systemd services ---
echo "🛠 Enabling systemd services..."
for service in /home/pi/growpro/services/*.service; do
    sudo cp "$service" /etc/systemd/system/
    sudo systemctl enable --now "$(basename "$service")"
done


# --- [11] Enable I2C interface ---
echo "🔌 Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0


# --- [12] Enable pigpiod daemon ---
echo "📡 Enabling pigpiod GPIO daemon..."
sudo systemctl enable pigpiod
sudo systemctl start pigpiod


# --- [13] Set hostname ---
echo "📛 Setting hostname to growpro..."
sudo hostnamectl set-hostname growpro
sudo sed -i 's/127.0.1.1.*/127.0.1.1\tgrowpro/' /etc/hosts


# --- [14] Auto-reboot on kernel panic ---
echo "🛡 Enabling auto-reboot on kernel panic..."
if ! grep -q "kernel.panic" /etc/sysctl.conf; then
    echo "kernel.panic = 10" | sudo tee -a /etc/sysctl.conf
else
    sudo sed -i 's/^kernel\.panic.*/kernel.panic = 10/' /etc/sysctl.conf
fi
sudo sysctl -p


# --- [15] Ready and reboot ---
echo "✅ GrowPro Setup complete."

# Show system access info
HOSTNAME=$(hostname)
IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo ""
echo "📡 Hostname:  $HOSTNAME"
echo "🌐 IP Address: $IP"
echo "🔲 GrowPro: http://$HOSTNAME:1880/dashboard/home"
echo "🔲 GrowPro (via IP): http://$IP:1880/dashboard/home"
echo ""

read -p "🔄 Setup is complete. A reboot is strongly recommended to apply all changes. Reboot now? [Y/n]: " answer
case "${answer,,}" in
    y|yes|"")
        echo "🔁 Rebooting now..."
        sudo reboot
        ;;
    *)
        echo "⚠️ Reboot skipped. Please reboot manually later to ensure everything works properly."
        ;;
esac



