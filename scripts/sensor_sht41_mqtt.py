import time
import board
import adafruit_sht4x
import paho.mqtt.client as mqtt

# MQTT Einstellungen
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_TEMP = "growpro/sensor/sht41/temperature"
MQTT_TOPIC_HUM = "growpro/sensor/sht41/humidity"

# MQTT Client einrichten
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# Sensor initialisieren (in Funktion, damit man neu starten kann)
def init_sensor():
    try:
        i2c = board.I2C()
        sensor = adafruit_sht4x.SHT4x(i2c)
        sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
        print("SHT41 initialisiert.")
        return sensor
    except Exception as e:
        print(f"SHT41 Init-Fehler: {e}")
        return None

sensor = init_sensor()

# Hauptloop
try:
    while True:
        if sensor is None:
            print("Versuche, Sensor neu zu initialisieren...")
            sensor = init_sensor()
            time.sleep(5)
            continue

        try:
            temperature, humidity = sensor.measurements
            print(f"Temp: {temperature:.2f} °C, RH: {humidity:.2f} %")
            client.publish(MQTT_TOPIC_TEMP, f"{temperature:.2f}")
            client.publish(MQTT_TOPIC_HUM, f"{humidity:.2f}")
        except Exception as e:
            print(f"Messfehler: {e}")
            sensor = None  # Nächste Runde -> neu initialisieren

        time.sleep(10)

except KeyboardInterrupt:
    print("Beendet.")
    client.loop_stop()
    client.disconnect()
