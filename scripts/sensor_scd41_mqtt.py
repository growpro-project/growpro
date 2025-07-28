import time
import board
import busio
import adafruit_scd4x
from adafruit_bme280 import basic
import paho.mqtt.client as mqtt
from math import pow

# MQTT Einstellungen
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# MQTT Topics
TOPIC_TEMP_SCD = "growpro/sensor/scd41/temperature"
TOPIC_HUM_SCD = "growpro/sensor/scd41/humidity"
TOPIC_CO2 = "growpro/sensor/scd41/co2"

TOPIC_TEMP_BME = "growpro/sensor/bme280/temperature"
TOPIC_HUM_BME = "growpro/sensor/bme280/humidity"
TOPIC_PRESSURE = "growpro/sensor/bme280/pressure"
TOPIC_ALTITUDE = "growpro/sensor/bme280/altitude"

TOPIC_CALIBRATE = "growpro/config/scd41/calibrate"
TOPIC_RESULT = "growpro/system/scd41/calibration_result"

SEA_LEVEL_PRESSURE_PA = 101325.0  # Standarddruck auf Meereshöhe

# MQTT Client Setup
client = mqtt.Client()

# Globale Sensorobjekte
sensor_scd41 = None
sensor_bme280 = None

def calculate_altitude(pressure_pa, sea_level_pa=SEA_LEVEL_PRESSURE_PA):
    """
    Berechnet die Höhe (in m) aus Druck (Pa)
    """
    if pressure_pa <= 0:
        return None
    alt_m = 44330.0 * (1.0 - pow(pressure_pa / sea_level_pa, 1.0 / 5.255))
    return round(alt_m, 2)

def init_sensors():
    global sensor_scd41, sensor_bme280
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        print("⏳ Warte auf I2C-Bus...")
        while not i2c.try_lock():
            pass

        devices = i2c.scan()
        print("📍 Gefundene I2C-Adressen:", [hex(d) for d in devices])
        i2c.unlock()

        sensor_scd41 = adafruit_scd4x.SCD4X(i2c)
        sensor_scd41.start_periodic_measurement()
        print("✅ SCD41 initialisiert.")

        time.sleep(1)  # Kleine Pause, damit der Bus stabil bleibt

        #sensor_bme280 = basic.Adafruit_BME280_I2C(i2c)
        sensor_bme280 = basic.Adafruit_BME280_I2C(i2c, address=0x76)

        print("✅ BME280 initialisiert.")

    except Exception as e:
        print(f"❌ Fehler bei der Initialisierung: {e}")
        sensor_scd41 = None
        sensor_bme280 = None

def perform_calibration():
    global sensor_scd41
    if sensor_scd41 is None:
        print("⚠️ Sensor nicht initialisiert.")
        client.publish(TOPIC_RESULT, "❌ Sensor nicht bereit für Kalibrierung")
        return

    print("🔧 Starte manuelle Kalibrierung auf 400ppm...")
    print("⏳ Voraussetzung: Sensor lief mindestens 10 Minuten an Frischluft!")

    try:

        print("⏹️ Stoppe laufende Messung...")
        sensor_scd41.stop_periodic_measurement()
        time.sleep(1)

        print("🚫 Deaktiviere ASC...")
        sensor_scd41.automatic_self_calibration = False

        # https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_trend_gl.txt
        # NOAA Global CO2 average 09.07.2025 425 ppm.
        print("🎯 Führe Kalibrierung auf 425ppm durch...")
        sensor_scd41.force_calibration(425)

        print("💾 Speichere Kalibrierung dauerhaft...")
        sensor_scd41.persist_settings()

        print("✅ Kalibrierung erfolgreich.")
        client.publish(TOPIC_RESULT, "✅ Kalibrierung erfolgreich bei 400ppm (ASC deaktiviert & gespeichert)")

    except Exception as e:
        print(f"❌ Fehler bei Kalibrierung: {e}")
        client.publish(TOPIC_RESULT, f"❌ Kalibrierung fehlgeschlagen: {e}")

    finally:
        print("⏳ Warte 30 Sekunden vor Neustart...")
        time.sleep(30)
        try:
            print("▶️ Starte Messung erneut...")
            sensor_scd41.start_periodic_measurement()
        except Exception as e:
            print(f"⚠️ Fehler beim Neustarten der Messung: {e}")
            client.publish(TOPIC_RESULT, f"⚠️ Fehler beim Neustart: {e}")

def on_message(client, userdata, msg):
    if msg.topic == TOPIC_CALIBRATE:
        perform_calibration()

# MQTT Setup
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()
client.subscribe(TOPIC_CALIBRATE)

# Sensoren initialisieren
init_sensors()

try:
    while True:
        if sensor_scd41 is None or sensor_bme280 is None:
            print("🔄 Versuche, Sensoren neu zu initialisieren...")
            init_sensors()
            time.sleep(5)
            continue

        try:
            # BME280 Werte
            pressure_hpa = sensor_bme280.pressure
            pressure_pa = pressure_hpa * 100
            temp_bme = sensor_bme280.temperature
            hum_bme = sensor_bme280.humidity
            altitude = calculate_altitude(pressure_pa)

            # Druck an SCD41 übergeben
            sensor_scd41.set_ambient_pressure(int(pressure_hpa))

            # Publish BME280-Daten
            client.publish(TOPIC_PRESSURE, f"{pressure_hpa:.2f}")
            client.publish(TOPIC_TEMP_BME, f"{temp_bme:.2f}")
            client.publish(TOPIC_HUM_BME, f"{hum_bme:.2f}")
            if altitude is not None:
                client.publish(TOPIC_ALTITUDE, f"{altitude:.2f}")

            print(f"📊 BME280 | Temp: {temp_bme:.2f} °C | RH: {hum_bme:.2f} % | P: {pressure_hpa:.2f} hPa | Alt: {altitude} m")

            if sensor_scd41.data_ready:
                co2 = sensor_scd41.CO2
                temp_scd = sensor_scd41.temperature
                hum_scd = sensor_scd41.relative_humidity

                print(f"📡 SCD41 | CO2: {co2} ppm | Temp: {temp_scd:.2f} °C | RH: {hum_scd:.2f} %")
                client.publish(TOPIC_CO2, f"{co2}")
                client.publish(TOPIC_TEMP_SCD, f"{temp_scd:.2f}")
                client.publish(TOPIC_HUM_SCD, f"{hum_scd:.2f}")

        except Exception as e:
            print(f"❌ Messfehler: {e}")
            sensor_scd41 = None
            sensor_bme280 = None

        time.sleep(10)

except KeyboardInterrupt:
    print("🛑 Beendet durch Benutzer.")
    client.loop_stop()
    client.disconnect()
