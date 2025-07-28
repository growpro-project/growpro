# import time
# import board
# import adafruit_sht4x
# import paho.mqtt.client as mqtt

# # MQTT Einstellungen
# MQTT_BROKER = "localhost"
# MQTT_PORT = 1883
# MQTT_TOPIC_TEMP = "growpro/sensor/sht41/temperature"
# MQTT_TOPIC_HUM = "growpro/sensor/sht41/humidity"

# # Anderer i2c bus
# # Aktivierung via /boot/config.txt)
# # Beispiel: i2c-3 auf GPIO 4/5 aktivieren
# # dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=4,i2c_gpio_scl=5
# # bus=3 – der gewünschte I²C-Bus
# # i2c_gpio_sda=4 – SDA-Pin (GPIO 4)
# # i2c_gpio_scl=5 – SCL-Pin (GPIO 5)
# # Dann:
# # sudo reboot

# # Sensor initialisieren
# # 👉 I²C-Bus 3 verwenden (nach vorheriger Aktivierung via /boot/config.txt)
# #i2c = busio.I2C(scl=board.SCL, sda=board.SDA, busnum=3)
# i2c = board.I2C()
# sensor = adafruit_sht4x.SHT4x(i2c)
# sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
# print("SHT41 initialisiert.")

# # MQTT verbinden
# client = mqtt.Client()
# client.connect(MQTT_BROKER, MQTT_PORT, 60)

# # Mess-Schleife
# try:
#     while True:
#         temperature, relative_humidity = sensor.measurements
#         print(f"Temp: {temperature:.2f} °C, RH: {relative_humidity:.2f} %")

#         # Werte senden
#         client.publish(MQTT_TOPIC_TEMP, f"{temperature:.2f}")
#         client.publish(MQTT_TOPIC_HUM, f"{relative_humidity:.2f}")

#         time.sleep(10)  # alle 10 Sekunden
# except KeyboardInterrupt:
#     print("Beendet.")
#     client.disconnect()

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


