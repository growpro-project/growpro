![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/logo/logo.svg)




An all-in-one Raspberry Pi setup with Node-RED, Docker, InfluxDB, and sensor integration.

## 🚀 Installation Instructions

⚠️ **Important:** This project assumes the default Raspberry Pi user is `pi`.  
If you're using a different username, you'll need to adjust all paths and services manually.

### Installation

```bash
git clone https://github.com/growpro-project/growpro.git /home/pi/growpro
cd /home/pi/growpro
bash setup.sh
```


This will:

Install system dependencies (Python, Docker, Node-RED, etc.)

Set up a Python virtual environment and install required packages

Configure and enable Node-RED with predefined flows and settings

Install and run InfluxDB via Docker

Set up MQTT (Mosquitto) and systemd services

Configure the I²C interface

Set the hostname to growpro
