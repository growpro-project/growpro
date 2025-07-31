# This project is under construction. More coming soon.
A plug & play plant monitoring and automation system for Raspberry Pi.


![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/logo/logo.svg)




An all-in-one Raspberry Pi setup with Node-RED, Docker, InfluxDB, and sensor integration.
This project was designed to be as simple as possible for people with no prior knowledge of ESPs, Home Assistant, or YAML configuration.
It runs on a Raspberry Pi 3B+ or newer and requires only minimal soldering, basic tinkering, and optionally some 3D printing.

The goal: plug & play automation with maximum ease and minimal setup effort.

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

### Funktions so far

- Email Alerts
- Live cam and timelaps recordings
- VPD Graph
- PID and Bang Bang



## 📷 Sneak peek screenshots – more to come!
### Dashboard
![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/screenshots/dashboard.png)

### Settings
![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/screenshots/settings.png)

### InfluxDB
![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/screenshots/influx.png)

### Live
![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/screenshots/live.png)

### VPD
![Logo](https://raw.githubusercontent.com/growpro-project/growpro-assets/main/images/screenshots/vpd.png)
