#!/bin/bash
set -e  # Exit script on any error

echo "🚀 Starting GrowPro Setup..."

# --- [1] Install system packages ---
echo "📦 Installing system packages..."
sudo apt update && sudo apt install -y \
    samba samba-common-bin \
    mosquitto mosquitto-clients \
    ffmpeg

# --- [2] Configure Samba (optional) ---
echo "🗂 Configuring Samba..."
echo -e "growpro\ngrowpro" | sudo smbpasswd -a pi || true
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

# --- [6] Enable Docker service ---
echo "🐳 Enabling Docker..."
sudo systemctl enable --now docker

# --- [7] Start InfluxDB Docker container ---
echo "📦 Starting InfluxDB Docker container..."
docker run -d \
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
echo "📛 Setting hostname..."
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

echo "✅ GrowPro Setup complete."
