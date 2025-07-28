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

