# import time
# import board
# import busio
# import adafruit_mlx90614
# import paho.mqtt.client as mqtt

# # MQTT-Konfig
# MQTT_BROKER = "localhost"
# TOPIC_AMBIENT = "growpro/sensor/mlx90614/ambient"
# TOPIC_OBJECT = "growpro/sensor/mlx90614/object"

# # I2C & Sensor
# # Bus 3 statt Standardbus (i2c-1)
# #i2c = busio.I2C(scl=board.SCL, sda=board.SDA, busnum=3)
# i2c = busio.I2C(board.SCL, board.SDA)
# mlx = adafruit_mlx90614.MLX90614(i2c)

# # MQTT-Client einrichten
# client = mqtt.Client()
# client.connect(MQTT_BROKER, 1883, 60)

# # Loop
# try:
#     while True:
#         ambient = round(mlx.ambient_temperature, 2)
#         object_temp = round(mlx.object_temperature, 2)

#         client.publish(TOPIC_AMBIENT, ambient)
#         client.publish(TOPIC_OBJECT, object_temp)

#         print(f"Ambient: {ambient} °C | Object: {object_temp} °C")

#         time.sleep(5)
# except KeyboardInterrupt:
#     print("Beendet.")

import time
import board
import busio
import adafruit_mlx90614
import paho.mqtt.client as mqtt

# MQTT-Konfig
MQTT_BROKER = "localhost"
TOPIC_AMBIENT = "growpro/sensor/mlx90614/ambient"
TOPIC_OBJECT = "growpro/sensor/mlx90614/object"

# MQTT-Client einrichten
client = mqtt.Client()
client.connect(MQTT_BROKER, 1883, 60)
client.loop_start()  # Optional für bessere Stabilität

def init_sensor():
    """Versucht, den Sensor zu initialisieren, mit Retry bei Fehlern."""
    while True:
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            mlx = adafruit_mlx90614.MLX90614(i2c)
            print("✅ Sensor initialisiert")
            return mlx
        except Exception as e:
            print(f"⚠️ Sensor nicht gefunden: {e}")
            print("↻ Neuer Versuch in 2 Sekunden...")
            time.sleep(2)

def main():
    sensor = init_sensor()
    while True:
        try:
            ambient = round(sensor.ambient_temperature, 2)
            object_temp = round(sensor.object_temperature, 2)

            client.publish(TOPIC_AMBIENT, ambient)
            client.publish(TOPIC_OBJECT, object_temp)

            print(f"🌡 Ambient: {ambient} °C | Object: {object_temp} °C")
            time.sleep(10)

        except Exception as e:
            print(f"❌ Fehler beim Lesen: {e}")
            print("🔄 Versuche Sensor neu zu verbinden...")
            time.sleep(2)
            sensor = init_sensor()

try:
    main()
except KeyboardInterrupt:
    print("🛑 Beendet.")
    client.loop_stop()
