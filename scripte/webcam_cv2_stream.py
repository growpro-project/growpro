# from flask import Flask, Response
# import cv2

# app = Flask(__name__)
# camera = cv2.VideoCapture(0)

# def gen_frames():
#     while True:
#         success, frame = camera.read()
#         if not success:
#             break
#         else:
#             ret, buffer = cv2.imencode('.jpg', frame)
#             frame = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# @app.route('/video_feed')
# def video_feed():
#     return Response(gen_frames(),
#                     mimetype='multipart/x-mixed-replace; boundary=frame')

# @app.route('/')
# def index():
#     return "Webcam läuft unter /video_feed"

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=False)

import cv2
import threading
import time
import paho.mqtt.client as mqtt

import numpy as np

from flask import Flask, Response

import logging
logging.basicConfig(level=logging.DEBUG)

# Overlay-Daten
overlay = {"temperature": None, "humidity": None}

#overlay_enabled = True  # default: Overlay AN
from threading import Event

overlay_enabled_flag = Event()
overlay_enabled_flag.set()  # Standard: aktiviert

# MQTT-Konfiguration
MQTT_BROKER = "localhost"
MQTT_TOPIC_TEMP = "growpro/sensor/sht41/temperature"
MQTT_TOPIC_HUM = "growpro/sensor/sht41/humidity"


def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position

    padding = 10
    radius = 10

    # Hintergrund-Rechteck (mit Transparenz und gerundeten Ecken)
    overlay = frame.copy()
    bg_color = (50, 50, 50)  # Grau
    alpha = 0.5              # Transparenz

    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding

    # Position anpassen
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    # Abgerundetes Rechteck zeichnen (4 Kreise + 4 Rechtecke)
    sub_img = overlay[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.zeros_like(sub_img, dtype=np.uint8)
    rect_bg[:] = bg_color

    cv2.rectangle(rect_bg, (radius, 0), (rect_width - radius, rect_height), bg_color, -1)
    cv2.rectangle(rect_bg, (0, radius), (rect_width, rect_height - radius), bg_color, -1)
    cv2.circle(rect_bg, (radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (radius, rect_height - radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, rect_height - radius), radius, bg_color, -1)

    # Transparenz anwenden
    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img

    # Text drauf
    cv2.putText(overlay, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return overlay


# MQTT Callback
def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"[MQTT] {msg.topic}: {payload}")
    global overlay_enabled  # Wichtig!

    if msg.topic == MQTT_TOPIC_TEMP:
        overlay["temperature"] = round(float(payload), 1)
    elif msg.topic == MQTT_TOPIC_HUM:
        overlay["humidity"] = round(float(payload), 1)
    elif msg.topic == "growpro/gui/cam-overlay/enable":
        if payload.lower() == "true":
            overlay_enabled_flag.set()
        else:
            overlay_enabled_flag.clear()
        print(f"[Overlay] overlay_enabled = {overlay_enabled_flag.is_set()}")


def start_mqtt():
    logging.info("⚡ MQTT-Thread läuft!")
    try:
        client = mqtt.Client()
        client.on_connect = lambda client, userdata, flags, rc: print(f"✅ Connected with result code {rc}")
        client.on_message = on_message
        client.connect("127.0.0.1", 1883, 60)
        client.subscribe([
            (MQTT_TOPIC_TEMP, 0),
            (MQTT_TOPIC_HUM, 0),
            ("growpro/gui/cam-overlay/enable", 0)   # <<< Nicht vergessen!
        ])
        client.loop_forever()
    except Exception as e:
        logging.error(f"MQTT-Fehler: {e}")


# Flask-Server
app = Flask(__name__)

# Kamera starten
#camera = cv2.VideoCapture(0)

# Kamera starten – automatisch finden
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, frame = cam.read()
            if ret:
                print(f"🎥 Kamera gefunden unter /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine funktionierende Kamera gefunden")

camera = find_camera()

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break

        # Text für Overlay vorbereiten
        temp = overlay["temperature"]
        hum = overlay["humidity"]
        text = ""
        if temp is not None:
            text += f"Temp: {temp}C  "
        if hum is not None:
            text += f"RH: {hum}%"

        # Overlay einfügen
        if overlay_enabled_flag.is_set() and text:
            frame = draw_overlay(frame, text)

        # Bild komprimieren und senden
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        #time.sleep(0.05)  # (ca. 20FPS)
        #time.sleep(0.1)  # (ca. 10FPS)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

if __name__ == '__main__':
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    print("MQTT-Thread gestartet")
    logging.info("MQTT-Thread gestartet")

    app.run(host='0.0.0.0', port=5000)

#-------------------------------------------------------------------------------------------------------
#ok


import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
from flask import Flask, Response
import logging

logging.basicConfig(level=logging.DEBUG)

# Overlay-Daten als reiner Text
overlay_text = ""

# Overlay EIN/AUS Flag
from threading import Event
overlay_enabled_flag = Event()
overlay_enabled_flag.set()  # Standard: aktiviert

# MQTT-Konfiguration
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"

# Overlay zeichnen
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position

    padding = 10
    radius = 10

    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5

    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.zeros_like(sub_img, dtype=np.uint8)
    rect_bg[:] = bg_color

    cv2.rectangle(rect_bg, (radius, 0), (rect_width - radius, rect_height), bg_color, -1)
    cv2.rectangle(rect_bg, (0, radius), (rect_width, rect_height - radius), bg_color, -1)
    cv2.circle(rect_bg, (radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (radius, rect_height - radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, rect_height - radius), radius, bg_color, -1)

    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img

    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return overlay_img

# MQTT Callback
def on_message(client, userdata, msg):
    global overlay_text
    payload = msg.payload.decode()
    print(f"[MQTT] {msg.topic}: {payload}")

    if msg.topic == MQTT_TOPIC_TEXT:
        overlay_text = payload
    elif msg.topic == MQTT_TOPIC_ENABLE:
        if payload.lower() == "true":
            overlay_enabled_flag.set()
        else:
            overlay_enabled_flag.clear()
        print(f"[Overlay] overlay_enabled = {overlay_enabled_flag.is_set()}")

# MQTT-Start
def start_mqtt():
    logging.info("⚡ MQTT-Thread läuft!")
    try:
        client = mqtt.Client()
        client.on_connect = lambda client, userdata, flags, rc: print(f"✅ Connected with result code {rc}")
        client.on_message = on_message
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe([
            (MQTT_TOPIC_TEXT, 0),
            (MQTT_TOPIC_ENABLE, 0)
        ])
        client.loop_forever()
    except Exception as e:
        logging.error(f"MQTT-Fehler: {e}")

# Flask-Server
app = Flask(__name__)

# Kamera automatisch finden
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, frame = cam.read()
            if ret:
                print(f"🎥 Kamera gefunden unter /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine funktionierende Kamera gefunden")

camera = find_camera()

# Video-Frames generieren
def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break

        if overlay_enabled_flag.is_set() and overlay_text:
            frame = draw_overlay(frame, overlay_text)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

if __name__ == '__main__':
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    print("MQTT-Thread gestartet")
    logging.info("MQTT-Thread gestartet")

    app.run(host='0.0.0.0', port=5000)


########################################################################################################################

import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
from flask import Flask, Response
import logging
import os
from datetime import datetime
from threading import Event

logging.basicConfig(level=logging.DEBUG)

# --- MQTT Topics ---
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# --- Global State ---
overlay_text = ""
overlay_enabled_flag = Event()
overlay_enabled_flag.set()

timelapse_interval_day = 60
timelapse_interval_night = 1800
timelapse_path = "/home/pi/growpro/timelapse"
timelapse_enabled = Event()
timelapse_enabled.clear()
light_on_flag = Event()
light_on_flag.clear()

latest_frame = None
camera_lock = threading.Lock()

def interrupted_sleep(check_interval, event):
    total = 0
    while total < check_interval:
        if not event.is_set():
            return False
        time.sleep(1)
        total += 1
    return True



# --- Overlay Funktion ---
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position
    padding = 10
    radius = 10
    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5
    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.zeros_like(sub_img, dtype=np.uint8)
    rect_bg[:] = bg_color

    # Abgerundete Ecken
    cv2.rectangle(rect_bg, (radius, 0), (rect_width - radius, rect_height), bg_color, -1)
    cv2.rectangle(rect_bg, (0, radius), (rect_width, rect_height - radius), bg_color, -1)
    cv2.circle(rect_bg, (radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (radius, rect_height - radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, rect_height - radius), radius, bg_color, -1)

    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return overlay_img

# --- MQTT Callback ---
def on_message(client, userdata, msg):
    global overlay_text, timelapse_interval_day, timelapse_interval_night, timelapse_path
    payload = msg.payload.decode()
    logging.debug(f"[MQTT] {msg.topic}: {payload}")

    if msg.topic == MQTT_TOPIC_TEXT:
        overlay_text = payload

    elif msg.topic == MQTT_TOPIC_ENABLE:
        overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
        try:
            timelapse_interval_day = int(payload)
        except ValueError:
            logging.warning("Ungültiger Tagesintervall")

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
        try:
            timelapse_interval_night = int(payload)
        except ValueError:
            logging.warning("Ungültiger Nachtintervall")

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_PATH:
        timelapse_path = payload.strip()

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
        timelapse_enabled.set() if payload.lower() == "true" else timelapse_enabled.clear()

    elif msg.topic == MQTT_TOPIC_LIGHTON:
        logging.debug(f"[MQTT] {msg.topic}: {payload}")
        if payload.lower() == "true":
            light_on_flag.set()
            logging.info("[Light] Licht ist AN")
        else:
            light_on_flag.clear()
            logging.info("[Light] Licht ist AUS")


def start_mqtt():
    client = mqtt.Client()
    client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT verbunden: {rc}")
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe([
        (MQTT_TOPIC_TEXT, 0),
        (MQTT_TOPIC_ENABLE, 0),
        (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
        (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
        (MQTT_TOPIC_TIMELAPSE_PATH, 0),
        (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
        (MQTT_TOPIC_LIGHTON, 0),
    ])
    client.loop_forever()

# --- Kamera finden ---
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, _ = cam.read()
            if ret:
                logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine Kamera gefunden")

camera = find_camera()

# --- Frame-Grabber Thread ---
def frame_grabber():
    global latest_frame
    while True:
        ret, frame = camera.read()
        if ret:
            with camera_lock:
                latest_frame = frame.copy()
        time.sleep(0.1)

# --- Video Feed ---
def gen_frames():
    while True:
        with camera_lock:
            frame = latest_frame.copy() if latest_frame is not None else None

        if frame is None:
            continue

        if overlay_enabled_flag.is_set() and overlay_text:
            frame = draw_overlay(frame, overlay_text)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# --- Timelapse Worker ---
def timelapse_worker():
    logging.info("📸 Timelapse-Thread gestartet")
    output_dir = None

    while True:
        if timelapse_enabled.is_set():
            ret, frame = camera.read()
            if ret:
                # Ordner beim ersten Bild erstellen
                if output_dir is None:
                    timestamp_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    output_dir = os.path.join(timelapse_path, timestamp_dir)
                    os.makedirs(output_dir, exist_ok=True)
                    logging.info(f"[Timelapse] Neuer Ordner: {output_dir}")

                # Bild speichern
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(output_dir, f"img_{timestamp}.jpg")
                cv2.imwrite(filename, frame)
                logging.info(f"[Timelapse] Bild gespeichert: {filename}")

            # 💡 Lichtstatus debuggen
            logging.debug(f"[Timelapse] Lichtstatus: {'Tag' if light_on_flag.is_set() else 'Nacht'}")

            # Intervall je nach Lichtstatus
            interval = timelapse_interval_day if light_on_flag.is_set() else timelapse_interval_night
            if not interrupted_sleep(interval, timelapse_enabled):
                logging.info("[Timelapse] Abgebrochen während Wartezeit")
                output_dir = None
        else:
            # Wenn deaktiviert, warten bis reaktiviert
            time.sleep(1)


# --- Flask Webserver ---
app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

# --- Main ---
if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    threading.Thread(target=frame_grabber, daemon=True).start()
    threading.Thread(target=timelapse_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)


################################
import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
from flask import Flask, Response
import logging
import os
from datetime import datetime
from threading import Event

logging.basicConfig(level=logging.DEBUG)

# --- MQTT Topics ---
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# --- Global State ---
overlay_text = ""
overlay_enabled_flag = Event()
overlay_enabled_flag.set()

timelapse_interval_day = 60
timelapse_interval_night = 1800
timelapse_path = "/home/pi/growpro/timelapse"
timelapse_enabled = Event()
timelapse_enabled.clear()
light_on_flag = Event()
light_on_flag.clear()

latest_frame = None
camera_lock = threading.Lock()

def interrupted_sleep(check_interval, event):
    total = 0
    while total < check_interval:
        if not event.is_set():
            return False
        time.sleep(1)
        total += 1
    return True



# --- Overlay Funktion ---
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position
    padding = 10
    radius = 10
    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5
    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.zeros_like(sub_img, dtype=np.uint8)
    rect_bg[:] = bg_color

    # Abgerundete Ecken
    cv2.rectangle(rect_bg, (radius, 0), (rect_width - radius, rect_height), bg_color, -1)
    cv2.rectangle(rect_bg, (0, radius), (rect_width, rect_height - radius), bg_color, -1)
    cv2.circle(rect_bg, (radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (radius, rect_height - radius), radius, bg_color, -1)
    cv2.circle(rect_bg, (rect_width - radius, rect_height - radius), radius, bg_color, -1)

    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return overlay_img

# --- MQTT Callback ---
def on_message(client, userdata, msg):
    global overlay_text, timelapse_interval_day, timelapse_interval_night, timelapse_path
    payload = msg.payload.decode()
    logging.debug(f"[MQTT] {msg.topic}: {payload}")

    if msg.topic == MQTT_TOPIC_TEXT:
        overlay_text = payload

    elif msg.topic == MQTT_TOPIC_ENABLE:
        overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
        try:
            timelapse_interval_day = int(payload)
        except ValueError:
            logging.warning("Ungültiger Tagesintervall")

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
        try:
            timelapse_interval_night = int(payload)
        except ValueError:
            logging.warning("Ungültiger Nachtintervall")

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_PATH:
        timelapse_path = payload.strip()

    elif msg.topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
        timelapse_enabled.set() if payload.lower() == "true" else timelapse_enabled.clear()

    elif msg.topic == MQTT_TOPIC_LIGHTON:
        logging.debug(f"[MQTT] {msg.topic}: {payload}")
        if payload.lower() == "true":
            light_on_flag.set()
            logging.info("[Light] Licht ist AN")
        else:
            light_on_flag.clear()
            logging.info("[Light] Licht ist AUS")


def start_mqtt():
    client = mqtt.Client()
    client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT verbunden: {rc}")
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe([
        (MQTT_TOPIC_TEXT, 0),
        (MQTT_TOPIC_ENABLE, 0),
        (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
        (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
        (MQTT_TOPIC_TIMELAPSE_PATH, 0),
        (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
        (MQTT_TOPIC_LIGHTON, 0),
    ])
    client.loop_forever()

# --- Kamera finden ---
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, _ = cam.read()
            if ret:
                logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine Kamera gefunden")

camera = find_camera()

# --- Frame-Grabber Thread ---
def frame_grabber():
    global latest_frame
    while True:
        ret, frame = camera.read()
        if ret:
            with camera_lock:
                latest_frame = frame.copy()
        time.sleep(0.1)

# --- Video Feed ---
# def gen_frames():
#     while True:
#         with camera_lock:
#             frame = latest_frame.copy() if latest_frame is not None else None

#         if frame is None:
#             continue

#         if overlay_enabled_flag.is_set() and overlay_text:
#             frame = draw_overlay(frame, overlay_text)

#         ret, buffer = cv2.imencode('.jpg', frame)
#         frame_bytes = buffer.tobytes()

#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# def gen_frames():
#     while True:
#         ret, frame = camera.read()
#         if not ret:
#             continue

#         if overlay_enabled_flag.is_set() and overlay_text:
#             frame = draw_overlay(frame, overlay_text)

#         ret, buffer = cv2.imencode('.jpg', frame)
#         frame_bytes = buffer.tobytes()

#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def gen_frames():
    while True:
        with camera_lock:
            frame = latest_frame.copy() if latest_frame is not None else None

        if frame is None:
            time.sleep(0.05)
            continue

        if overlay_enabled_flag.is_set() and overlay_text:
            frame = draw_overlay(frame, overlay_text)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# --- Timelapse Worker ---
# def timelapse_worker():
#     logging.info("📸 Timelapse-Thread gestartet")
#     output_dir = None

#     while True:
#         if timelapse_enabled.is_set():
#             ret, frame = camera.read()
#             if ret:
#                 # Ordner beim ersten Bild erstellen
#                 if output_dir is None:
#                     timestamp_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#                     output_dir = os.path.join(timelapse_path, timestamp_dir)
#                     os.makedirs(output_dir, exist_ok=True)
#                     logging.info(f"[Timelapse] Neuer Ordner: {output_dir}")

#                 # Bild speichern
#                 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#                 filename = os.path.join(output_dir, f"img_{timestamp}.jpg")
#                 cv2.imwrite(filename, frame)
#                 logging.info(f"[Timelapse] Bild gespeichert: {filename}")

#             # 💡 Lichtstatus debuggen
#             logging.debug(f"[Timelapse] Lichtstatus: {'Tag' if light_on_flag.is_set() else 'Nacht'}")

#             # Intervall je nach Lichtstatus
#             interval = timelapse_interval_day if light_on_flag.is_set() else timelapse_interval_night
#             if not interrupted_sleep(interval, timelapse_enabled):
#                 logging.info("[Timelapse] Abgebrochen während Wartezeit")
#                 output_dir = None
#         else:
#             # Wenn deaktiviert, warten bis reaktiviert
#             time.sleep(1)

# def timelapse_worker():
#     logging.info("📸 Timelapse-Thread gestartet")
#     output_dir = None

#     while True:
#         if timelapse_enabled.is_set():
#             with camera_lock:
#                 frame = latest_frame.copy() if latest_frame is not None else None

#             if frame is not None:
#                 if output_dir is None:
#                     timestamp_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#                     output_dir = os.path.join(timelapse_path, timestamp_dir)
#                     os.makedirs(output_dir, exist_ok=True)
#                     logging.info(f"[Timelapse] Neuer Ordner: {output_dir}")

#                 timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#                 filename = os.path.join(output_dir, f"img_{timestamp}.jpg")
#                 cv2.imwrite(filename, frame)
#                 logging.info(f"[Timelapse] Bild gespeichert: {filename}")

#             interval = timelapse_interval_day if light_on_flag.is_set() else timelapse_interval_night
#             if not interrupted_sleep(interval, timelapse_enabled):
#                 logging.info("[Timelapse] Abgebrochen während Wartezeit")
#                 output_dir = None
#         else:
#             time.sleep(1)

def timelapse_worker():
    logging.info("📸 Timelapse-Thread gestartet")
    output_dir = None

    while True:
        if timelapse_enabled.is_set():
            now = time.time()

            # Erstes Bild? Ordner anlegen.
            if output_dir is None:
                timestamp_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                output_dir = os.path.join(timelapse_path, timestamp_dir)
                os.makedirs(output_dir, exist_ok=True)
                logging.info(f"[Timelapse] Neuer Ordner: {output_dir}")

            # Aktuelles Frame holen (aus shared Buffer)
            with camera_lock:
                frame = latest_frame.copy() if latest_frame is not None else None

            if frame is not None:
                # Bild speichern
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(output_dir, f"img_{timestamp}.jpg")
                cv2.imwrite(filename, frame)
                logging.info(f"[Timelapse] Bild gespeichert: {filename}")
            else:
                logging.warning("[Timelapse] Kein Frame verfügbar!")

            # Intervall bestimmen
            interval = timelapse_interval_day if light_on_flag.is_set() else timelapse_interval_night
            logging.debug(f"[Timelapse] Licht: {'Tag' if light_on_flag.is_set() else 'Nacht'} | Intervall: {interval}s")

            # Bis zur nächsten Aufnahme schlafen
            next_capture = now + interval
            while time.time() < next_capture:
                if not timelapse_enabled.is_set():
                    output_dir = None
                    break
                time.sleep(0.5)
        else:
            time.sleep(1)


# --- Flask Webserver ---
app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

# --- Main ---
if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    threading.Thread(target=frame_grabber, daemon=True).start()
    threading.Thread(target=timelapse_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

####################################
# 1 thread


import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
import os
from flask import Flask, Response
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# --- Global States ---
overlay_text = ""
overlay_enabled_flag = threading.Event()
overlay_enabled_flag.set()

timelapse_enabled_flag = threading.Event()
timelapse_path = "/home/pi/growpro/timelapse"
interval_day = 60
interval_night = 1800
light_on = True

last_capture_time = 0

# --- MQTT Topics ---
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# --- Overlay ---
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position
    padding = 10
    radius = 10

    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5
    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    if top_left[1] < 0 or bottom_right[1] > overlay_img.shape[0] or bottom_right[0] > overlay_img.shape[1]:
        return frame

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.full_like(sub_img, bg_color, dtype=np.uint8)
    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return overlay_img

# --- MQTT Handler ---
def on_message(client, userdata, msg):
    global overlay_text, timelapse_path, interval_day, interval_night, light_on

    topic = msg.topic
    payload = msg.payload.decode().strip()
    logging.info(f"[MQTT] {topic}: {payload}")

    if topic == MQTT_TOPIC_TEXT:
        overlay_text = payload
    elif topic == MQTT_TOPIC_ENABLE:
        overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()
    elif topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
        timelapse_enabled_flag.set() if payload.lower() == "true" else timelapse_enabled_flag.clear()
    elif topic == MQTT_TOPIC_TIMELAPSE_PATH:
        timelapse_path = payload
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
        interval_day = int(payload)
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
        interval_night = int(payload)
    elif topic == MQTT_TOPIC_LIGHTON:
        light_on = payload.lower() == "true"

def start_mqtt():
    try:
        client = mqtt.Client()
        client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT connected: {rc}")
        client.on_message = on_message
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe([
            (MQTT_TOPIC_TEXT, 0),
            (MQTT_TOPIC_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_PATH, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
            (MQTT_TOPIC_LIGHTON, 0)
        ])
        client.loop_forever()
    except Exception as e:
        logging.error(f"[MQTT] Fehler: {e}")

# --- Kamera finden ---
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, _ = cam.read()
            if ret:
                logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine Kamera gefunden")

camera = find_camera()

# --- Timelapse speichern ---
def maybe_capture_timelapse(frame):
    global last_capture_time
    if not timelapse_enabled_flag.is_set():
        return

    now = time.time()
    interval = interval_day if light_on else interval_night

    if now - last_capture_time >= interval:
        last_capture_time = now

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dated_dir = os.path.join(timelapse_path, datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(dated_dir, exist_ok=True)
        filename = os.path.join(dated_dir, f"{timestamp}.jpg")
        cv2.imwrite(filename, frame)
        logging.info(f"📸 Timelapse gespeichert: {filename}")

# --- Flask Video ---
app = Flask(__name__)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.1)
            continue

        if overlay_enabled_flag.is_set() and overlay_text:
            frame = draw_overlay(frame, overlay_text)

        maybe_capture_timelapse(frame)

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        time.sleep(0.2)  # 5 FPS Limit

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    logging.info("📡 MQTT gestartet")
    app.run(host='0.0.0.0', port=5000, threaded=True)

########################################################################################

# + ffmpg auto umwandlung
# ordner %Y-%m-%d


# import cv2
# import threading
# import time
# import paho.mqtt.client as mqtt
# import numpy as np
# import os
# import subprocess
# from flask import Flask, Response
# import logging
# from datetime import datetime
# import glob

# logging.basicConfig(level=logging.INFO)

# # --- Global States ---
# overlay_text = ""
# overlay_enabled_flag = threading.Event()
# overlay_enabled_flag.set()

# timelapse_enabled_flag = threading.Event()
# timelapse_path = "/home/pi/growpro/timelapse"
# interval_day = 60
# interval_night = 1800
# light_on = True

# last_capture_time = 0

# # --- MQTT Topics ---
# MQTT_BROKER = "127.0.0.1"
# MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
# MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
# MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
# MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
# MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
# MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
# MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# # --- Overlay ---
# def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
#     font = cv2.FONT_HERSHEY_SIMPLEX
#     text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
#     text_width, text_height = text_size
#     x, y = position
#     padding = 10
#     radius = 10

#     overlay_img = frame.copy()
#     bg_color = (50, 50, 50)
#     alpha = 0.5
#     rect_width = text_width + 2 * padding
#     rect_height = text_height + 2 * padding
#     top_left = (x, y - text_height - padding)
#     bottom_right = (x + rect_width, y + padding)

#     if top_left[1] < 0 or bottom_right[1] > overlay_img.shape[0] or bottom_right[0] > overlay_img.shape[1]:
#         return frame

#     sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
#     rect_bg = np.full_like(sub_img, bg_color, dtype=np.uint8)
#     cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
#     overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
#     cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

#     return overlay_img

# # --- Timelapse zu Video konvertieren ---
# def convert_timelapse_to_video(folder):
#     jpg_files = sorted(glob.glob(os.path.join(folder, "*.jpg")))
#     if not jpg_files:
#         logging.info("[Timelapse] Keine Bilder zum Konvertieren.")
#         return

#     logging.info("[Timelapse] Konvertiere Bilder zu timelapse.mp4...")
#     output_file = os.path.join(folder, "timelapse.mp4")

#     try:
#         subprocess.run([
#             "ffmpeg",
#             "-y",
#             "-framerate", "30",
#             "-pattern_type", "glob",
#             "-i", os.path.join(folder, "img_*.jpg"),
#             "-c:v", "libx264",
#             "-pix_fmt", "yuv420p",
#             output_file
#         ], check=True)

#         # JPGs löschen
#         for f in jpg_files:
#             os.remove(f)

#         logging.info(f"[Timelapse] Video gespeichert unter: {output_file}")
#         logging.info(f"[Timelapse] {len(jpg_files)} Einzelbilder gelöscht.")
#     except Exception as e:
#         logging.error(f"[Timelapse] Fehler beim Konvertieren: {e}")

# # --- MQTT Handler ---
# def on_message(client, userdata, msg):
#     global overlay_text, timelapse_path, interval_day, interval_night, light_on

#     topic = msg.topic
#     payload = msg.payload.decode().strip()
#     logging.info(f"[MQTT] {topic}: {payload}")

#     if topic == MQTT_TOPIC_TEXT:
#         overlay_text = payload
#     elif topic == MQTT_TOPIC_ENABLE:
#         overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()
#     elif topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
#         was_enabled = timelapse_enabled_flag.is_set()
#         if payload.lower() == "true":
#             timelapse_enabled_flag.set()
#         else:
#             timelapse_enabled_flag.clear()
#             if was_enabled:
#                 last_folder = os.path.join(timelapse_path, datetime.now().strftime("%Y-%m-%d"))
#                 threading.Thread(target=convert_timelapse_to_video, args=(last_folder,), daemon=True).start()
#     elif topic == MQTT_TOPIC_TIMELAPSE_PATH:
#         timelapse_path = payload
#     elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
#         interval_day = int(payload)
#     elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
#         interval_night = int(payload)
#     elif topic == MQTT_TOPIC_LIGHTON:
#         light_on = payload.lower() == "true"

# def start_mqtt():
#     try:
#         client = mqtt.Client()
#         client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT connected: {rc}")
#         client.on_message = on_message
#         client.connect(MQTT_BROKER, 1883, 60)
#         client.subscribe([
#             (MQTT_TOPIC_TEXT, 0),
#             (MQTT_TOPIC_ENABLE, 0),
#             (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
#             (MQTT_TOPIC_TIMELAPSE_PATH, 0),
#             (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
#             (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
#             (MQTT_TOPIC_LIGHTON, 0)
#         ])
#         client.loop_forever()
#     except Exception as e:
#         logging.error(f"[MQTT] Fehler: {e}")

# # --- Kamera finden ---
# def find_camera(max_index=5):
#     for i in range(max_index):
#         cam = cv2.VideoCapture(i)
#         if cam.isOpened():
#             ret, _ = cam.read()
#             if ret:
#                 logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
#                 return cam
#         cam.release()
#     raise RuntimeError("❌ Keine Kamera gefunden")

# camera = find_camera()

# # --- Timelapse speichern ---
# def maybe_capture_timelapse(frame):
#     global last_capture_time
#     if not timelapse_enabled_flag.is_set():
#         return

#     now = time.time()
#     interval = interval_day if light_on else interval_night

#     if now - last_capture_time >= interval:
#         last_capture_time = now
#         timestamp = datetime.now().strftime("img_%Y-%m-%d_%H-%M-%S.jpg")
#         dated_dir = os.path.join(timelapse_path, datetime.now().strftime("%Y-%m-%d"))
#         os.makedirs(dated_dir, exist_ok=True)
#         filename = os.path.join(dated_dir, timestamp)
#         cv2.imwrite(filename, frame)
#         logging.info(f"📸 Timelapse gespeichert: {filename}")

# # --- Flask Video ---
# app = Flask(__name__)

# def gen_frames():
#     while True:
#         success, frame = camera.read()
#         if not success:
#             time.sleep(0.1)
#             continue

#         if overlay_enabled_flag.is_set() and overlay_text:
#             frame = draw_overlay(frame, overlay_text)

#         maybe_capture_timelapse(frame)

#         ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
#         if not ret:
#             continue

#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

#         time.sleep(0.2)  # ca. 5 FPS

# @app.route('/video_feed')
# def video_feed():
#     return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# @app.route('/')
# def index():
#     return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

# if __name__ == '__main__':
#     threading.Thread(target=start_mqtt, daemon=True).start()
#     logging.info("📡 MQTT gestartet")
#     app.run(host='0.0.0.0', port=5000, threaded=True)

########################################################################################################
# + ffmpg auto umwandlung
# ordner %Y-%m-%d_%H-%M-%S

import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
import os
import subprocess
from flask import Flask, Response
import logging
from datetime import datetime
import glob

logging.basicConfig(level=logging.INFO)

# --- Global States ---
overlay_text = ""
overlay_enabled_flag = threading.Event()
overlay_enabled_flag.set()

timelapse_enabled_flag = threading.Event()
timelapse_path = "/home/pi/growpro/timelapse"
interval_day = 60
interval_night = 1800
light_on = True
last_capture_time = 0
current_timelapse_folder = None

# --- MQTT Topics ---
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# --- Overlay ---
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position
    padding = 10

    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5
    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    if top_left[1] < 0 or bottom_right[1] > overlay_img.shape[0] or bottom_right[0] > overlay_img.shape[1]:
        return frame

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.full_like(sub_img, bg_color, dtype=np.uint8)
    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return overlay_img

# --- Timelapse zu Video konvertieren ---
def convert_timelapse_to_video(folder):
    jpg_files = sorted(glob.glob(os.path.join(folder, "img_*.jpg")))
    if not jpg_files:
        logging.info("[Timelapse] Keine Bilder zum Konvertieren.")
        return

    logging.info("[Timelapse] Konvertiere Bilder zu timelapse.mp4...")
    output_file = os.path.join(folder, "timelapse.mp4")

    try:
        # subprocess.run([
        #     "ffmpeg", "-y", "-framerate", "30", "-pattern_type", "glob",
        #     "-i", os.path.join(folder, "img_*.jpg"),
        #     "-c:v", "libx264", "-pix_fmt", "yuv420p", output_file
        # ], check=True)

        # subprocess.run([
        #     "nice", "-n", "15",
        #     "ffmpeg", "-y", "-framerate", "30", "-pattern_type", "glob",
        #     "-i", os.path.join(folder, "img_*.jpg"),
        #     "-c:v", "libx264", "-pix_fmt", "yuv420p",
        #     "-threads", "2",
        #     output_file
        # ], check=True)

        subprocess.run([
            "nice", "-n", "15",
            "ionice", "-c", "3",  # Best-effort I/O
            "ffmpeg", "-y", "-framerate", "15",  # Reduziere FPS!
            "-pattern_type", "glob",
            "-i", os.path.join(folder, "img_*.jpg"),
            "-c:v", "libx264", "-preset", "veryfast",  # beschleunigt -framerate 10 + -preset ultrafast 🚀 Massiv schneller
            "-pix_fmt", "yuv420p",
            "-threads", "1",  # Optional: noch weniger Last
            output_file
        ], check=True)

        for f in jpg_files:
            os.remove(f)

        logging.info(f"[Timelapse] Video gespeichert unter: {output_file}")
        logging.info(f"[Timelapse] {len(jpg_files)} Einzelbilder gelöscht.")
    except Exception as e:
        logging.error(f"[Timelapse] Fehler beim Konvertieren: {e}")

# --- MQTT Handler ---
def on_message(client, userdata, msg):
    global overlay_text, timelapse_path, interval_day, interval_night, light_on, current_timelapse_folder

    topic = msg.topic
    payload = msg.payload.decode().strip()
    logging.info(f"[MQTT] {topic}: {payload}")

    if topic == MQTT_TOPIC_TEXT:
        overlay_text = payload
    elif topic == MQTT_TOPIC_ENABLE:
        overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()
    elif topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
        was_enabled = timelapse_enabled_flag.is_set()
        if payload.lower() == "true":
            timelapse_enabled_flag.set()
            current_timelapse_folder = os.path.join(timelapse_path, datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            os.makedirs(current_timelapse_folder, exist_ok=True)
        else:
            timelapse_enabled_flag.clear()
            if was_enabled and current_timelapse_folder:
                threading.Thread(target=convert_timelapse_to_video, args=(current_timelapse_folder,), daemon=True).start()
                current_timelapse_folder = None
    elif topic == MQTT_TOPIC_TIMELAPSE_PATH:
        timelapse_path = payload
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
        interval_day = int(payload)
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
        interval_night = int(payload)
    elif topic == MQTT_TOPIC_LIGHTON:
        light_on = payload.lower() == "true"

def start_mqtt():
    try:
        client = mqtt.Client()
        client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT connected: {rc}")
        client.on_message = on_message
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe([
            (MQTT_TOPIC_TEXT, 0),
            (MQTT_TOPIC_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_PATH, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
            (MQTT_TOPIC_LIGHTON, 0)
        ])
        client.loop_forever()
    except Exception as e:
        logging.error(f"[MQTT] Fehler: {e}")

# --- Kamera finden ---
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, _ = cam.read()
            if ret:
                logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine Kamera gefunden")

camera = find_camera()

# --- Timelapse speichern ---
def maybe_capture_timelapse(frame):
    global last_capture_time, current_timelapse_folder
    if not timelapse_enabled_flag.is_set() or not current_timelapse_folder:
        return

    now = time.time()
    interval = interval_day if light_on else interval_night

    if now - last_capture_time >= interval:
        last_capture_time = now
        timestamp = datetime.now().strftime("img_%Y%m%d_%H%M%S.jpg")
        filename = os.path.join(current_timelapse_folder, timestamp)
        cv2.imwrite(filename, frame)
        logging.info(f"📸 Timelapse gespeichert: {filename}")

# --- Flask Video ---
app = Flask(__name__)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.1)
            continue

        raw_frame = frame.copy()  # Original speichern

        if overlay_enabled_flag.is_set() and overlay_text:
            frame = draw_overlay(frame, overlay_text)

        #maybe_capture_timelapse(frame) # save overlay
        maybe_capture_timelapse(raw_frame) # save without overlay

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        time.sleep(0.2)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    logging.info("📡 MQTT gestartet")
    app.run(host='0.0.0.0', port=5000, threaded=True)



########################################################################################################
########################################################################################################
########################################################################################################

import cv2
import threading
import time
import paho.mqtt.client as mqtt
import numpy as np
import os
import subprocess
from flask import Flask, Response
import logging
from datetime import datetime
import glob

logging.basicConfig(level=logging.INFO)

# --- Global States ---
overlay_text = ""
overlay_enabled_flag = threading.Event()
overlay_enabled_flag.set()

timelapse_enabled_flag = threading.Event()
camera_needed_flag = threading.Event()
camera_lock = threading.Lock()
latest_frame = None

overlay_clients_connected = 0
overlay_clients_lock = threading.Lock()

timelapse_path = "/home/pi/growpro/timelapse"
interval_day = 60
interval_night = 1800
light_on = True
last_capture_time = 0
current_timelapse_folder = None

# --- MQTT Topics ---
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC_TEXT = "growpro/gui/cam-overlay/text"
MQTT_TOPIC_ENABLE = "growpro/gui/cam-overlay/enable"
MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY = "growpro/gui/timelapse/interval_day"
MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT = "growpro/gui/timelapse/interval_night"
MQTT_TOPIC_TIMELAPSE_PATH = "growpro/gui/timelapse/path"
MQTT_TOPIC_TIMELAPSE_ENABLE = "growpro/gui/timelapse/enable"
MQTT_TOPIC_LIGHTON = "growpro/gui/timelapse/lightOn"

# --- Overlay ---
def draw_overlay(frame, text, position=(10, 30), font_scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size
    x, y = position
    padding = 10

    overlay_img = frame.copy()
    bg_color = (50, 50, 50)
    alpha = 0.5
    rect_width = text_width + 2 * padding
    rect_height = text_height + 2 * padding
    top_left = (x, y - text_height - padding)
    bottom_right = (x + rect_width, y + padding)

    if top_left[1] < 0 or bottom_right[1] > overlay_img.shape[0] or bottom_right[0] > overlay_img.shape[1]:
        return frame

    sub_img = overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]].copy()
    rect_bg = np.full_like(sub_img, bg_color, dtype=np.uint8)
    cv2.addWeighted(rect_bg, alpha, sub_img, 1 - alpha, 0, sub_img)
    overlay_img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = sub_img
    cv2.putText(overlay_img, text, (x + padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return overlay_img

# --- Timelapse zu Video konvertieren ---
def convert_timelapse_to_video(folder):
    jpg_files = sorted(glob.glob(os.path.join(folder, "img_*.jpg")))
    if not jpg_files:
        logging.info("[Timelapse] Keine Bilder zum Konvertieren.")
        return

    logging.info("[Timelapse] Konvertiere Bilder zu timelapse.mp4...")
    output_file = os.path.join(folder, "timelapse.mp4")

    try:
        subprocess.run([
            "nice", "-n", "15",
            "ionice", "-c", "3",  # Best-effort I/O
            "ffmpeg", "-y", "-framerate", "60",
            "-pattern_type", "glob",
            "-i", os.path.join(folder, "img_*.jpg"),
            "-c:v", "libx264", "-preset", "veryfast",  # -preset ultrafast 🚀 Massiv schneller
            "-pix_fmt", "yuv420p",
            "-threads", "2",  # Optional: noch weniger Last
            output_file
        ], check=True)

        for f in jpg_files:
            os.remove(f)

        logging.info(f"[Timelapse] Video gespeichert unter: {output_file}")
        logging.info(f"[Timelapse] {len(jpg_files)} Einzelbilder gelöscht.")
    except Exception as e:
        logging.error(f"[Timelapse] Fehler beim Konvertieren: {e}")

# --- Kamera finden ---
def find_camera(max_index=5):
    for i in range(max_index):
        cam = cv2.VideoCapture(i)
        if cam.isOpened():
            ret, _ = cam.read()
            if ret:
                logging.info(f"🎥 Kamera gefunden: /dev/video{i}")
                return cam
        cam.release()
    raise RuntimeError("❌ Keine Kamera gefunden")

# --- Timelapse speichern ---
def maybe_capture_timelapse(frame):
    global last_capture_time, current_timelapse_folder
    if not timelapse_enabled_flag.is_set() or not current_timelapse_folder:
        return

    now = time.time()
    interval = interval_day if light_on else interval_night

    if now - last_capture_time >= interval:
        last_capture_time = now
        timestamp = datetime.now().strftime("img_%Y%m%d_%H%M%S.jpg")
        filename = os.path.join(current_timelapse_folder, timestamp)
        cv2.imwrite(filename, frame)
        logging.info(f"📸 Timelapse gespeichert: {filename}")

# --- Kamera-Loop ---
def camera_loop():
    global latest_frame
    cam = None
    while True:
        if camera_needed_flag.is_set():
            if cam is None:
                try:
                    cam = find_camera()
                except Exception as e:
                    logging.error(f"[CameraLoop] Kamera konnte nicht geöffnet werden: {e}")
                    time.sleep(5)
                    continue

            success, frame = cam.read()
            if not success:
                logging.warning("[CameraLoop] Frame konnte nicht gelesen werden.")
                time.sleep(0.5)
                continue

            with camera_lock:
                latest_frame = frame.copy()

            if timelapse_enabled_flag.is_set():
                maybe_capture_timelapse(frame)

            time.sleep(0.2)
        else:
            if cam:
                cam.release()
                cam = None
                logging.info("[CameraLoop] Kamera freigegeben (nicht mehr benötigt).")
            time.sleep(1)

# --- MQTT Handler ---
def on_message(client, userdata, msg):
    global overlay_text, timelapse_path, interval_day, interval_night, light_on, current_timelapse_folder

    topic = msg.topic
    payload = msg.payload.decode().strip()
    logging.info(f"[MQTT] {topic}: {payload}")

    if topic == MQTT_TOPIC_TEXT:
        overlay_text = payload
    elif topic == MQTT_TOPIC_ENABLE:
        overlay_enabled_flag.set() if payload.lower() == "true" else overlay_enabled_flag.clear()
    elif topic == MQTT_TOPIC_TIMELAPSE_ENABLE:
        was_enabled = timelapse_enabled_flag.is_set()
        if payload.lower() == "true":
            timelapse_enabled_flag.set()
            camera_needed_flag.set()
            current_timelapse_folder = os.path.join(timelapse_path, datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            os.makedirs(current_timelapse_folder, exist_ok=True)
        else:
            timelapse_enabled_flag.clear()
            if overlay_clients_connected == 0:
                camera_needed_flag.clear()
            if was_enabled and current_timelapse_folder:
                threading.Thread(target=convert_timelapse_to_video, args=(current_timelapse_folder,), daemon=True).start()
                current_timelapse_folder = None
    elif topic == MQTT_TOPIC_TIMELAPSE_PATH:
        timelapse_path = payload
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY:
        interval_day = int(payload)
    elif topic == MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT:
        interval_night = int(payload)
    elif topic == MQTT_TOPIC_LIGHTON:
        light_on = payload.lower() == "true"

def start_mqtt():
    try:
        client = mqtt.Client()
        client.on_connect = lambda c, u, f, rc: logging.info(f"✅ MQTT connected: {rc}")
        client.on_message = on_message
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe([
            (MQTT_TOPIC_TEXT, 0),
            (MQTT_TOPIC_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_ENABLE, 0),
            (MQTT_TOPIC_TIMELAPSE_PATH, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_DAY, 0),
            (MQTT_TOPIC_TIMELAPSE_INTERVAL_NIGHT, 0),
            (MQTT_TOPIC_LIGHTON, 0)
        ])
        client.loop_forever()
    except Exception as e:
        logging.error(f"[MQTT] Fehler: {e}")

# --- Flask Video ---
app = Flask(__name__)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>GrowPro Live</h1><img src='/video_feed' style='width: 100%; max-width: 640px;' />"

def gen_frames():
    global overlay_clients_connected
    with overlay_clients_lock:
        overlay_clients_connected += 1
        camera_needed_flag.set()

    try:
        while True:
            with camera_lock:
                if latest_frame is None:
                    time.sleep(0.1)
                    continue
                frame = latest_frame.copy()

            if overlay_enabled_flag.is_set() and overlay_text:
                frame = draw_overlay(frame, overlay_text)

            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.2)
    finally:
        with overlay_clients_lock:
            overlay_clients_connected -= 1
            if overlay_clients_connected == 0 and not timelapse_enabled_flag.is_set():
                camera_needed_flag.clear()

if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    threading.Thread(target=camera_loop, daemon=True).start()
    logging.info("📡 MQTT & Kamera-Loop gestartet")
    app.run(host='0.0.0.0', port=5000, threaded=True)

