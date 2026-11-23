"""Virtual ESP32: behaves like the real board will, so the MQTT flow can be shown without hardware.

Like the professor's ESP32-C3 sketch it:
- subscribes to PREFIX/prediction and "turns on" an LED for each stored prediction
  (green = dog, blue = cat, yellow blinking = uncertain),
- publishes a JSON heartbeat to PREFIX/esp32/status every 5 seconds,
- publishes {"command": "SNAPSHOT"} to PREFIX/command when its "button" is pressed (Enter key),
  which makes the camera station save a photo.

Run:  .venv\\Scripts\\python virtual_esp32.py      (Enter = press the button, q + Enter = quit)
"""
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

MQTT_HOST = os.getenv("MQTT_HOST", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_PREFIX = os.getenv("MQTT_PREFIX", "catsdogs-vision/camilomed1").rstrip("/")
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp")  # or "websockets" (port 8083) if port 1883 is blocked
DEVICE = os.getenv("DEVICE_NAME", "virtual-ESP32")

TOPIC_PREDICTION = f"{MQTT_PREFIX}/prediction"
TOPIC_COMMAND = f"{MQTT_PREFIX}/command"
TOPIC_STATUS = f"{MQTT_PREFIX}/esp32/status"
LEDS = {"dog": "GREEN LED", "cat": "BLUE LED", "uncertain": "YELLOW LED (blinking)"}

message_number = 0
running = True


def log(text):
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        log(f"MQTT connection failed: {reason_code}")
        return
    log(f"Connected to {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(TOPIC_PREDICTION)
    client.subscribe(f"{MQTT_PREFIX}/backend/status")
    client.subscribe(f"{MQTT_PREFIX}/station/status")
    log(f"Subscribed to {TOPIC_PREDICTION}")


def on_message(client, userdata, msg):
    text = msg.payload.decode("utf-8", errors="replace")
    if msg.topic.endswith("/backend/status"):
        log(f"Backend is {text}")
        return
    if msg.topic.endswith("/station/status"):
        try:
            station = json.loads(text)
            log(f"Camera station '{station.get('camera')}' is {station.get('status')}")
        except ValueError:
            pass
        return
    try:
        p = json.loads(text)  # same idea as deserializeJson() in the Arduino code
    except ValueError:
        log(f"Invalid JSON: {text[:80]}")
        return
    label = p.get("label", "")
    led = LEDS.get(label, "no LED")
    source = f"{p.get('client')}/{p.get('source')}" + (f" ({p['mode']})" if p.get("mode") else "")
    log(f"Prediction: {label.upper()} {p.get('confidence', 0) * 100:.1f}% from {source}  ->  {led} ON for 2 s"
        + ("  + BEEP" if label in ("cat", "dog") else ""))


def heartbeat(client):
    """Same JSON as the professor's example: device, message, number."""
    global message_number
    while running:
        if client.is_connected():
            client.publish(TOPIC_STATUS, json.dumps({"device": DEVICE, "message": "alive", "number": message_number}))
            message_number += 1
        time.sleep(5)


def main():
    global running
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE}-{uuid.uuid4().hex[:6]}",
                         transport=MQTT_TRANSPORT)
    if MQTT_TRANSPORT == "websockets":
        client.ws_set_options(path="/mqtt")
    client.on_connect = on_connect
    client.on_message = on_message
    log(f"Connecting to MQTT broker {MQTT_HOST}:{MQTT_PORT} (prefix {MQTT_PREFIX})...")
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    threading.Thread(target=heartbeat, args=(client,), daemon=True).start()

    print("Press Enter to press the button (SNAPSHOT), or type q + Enter to quit.", flush=True)
    try:
        for line in sys.stdin:
            if line.strip().lower() == "q":
                break
            client.publish(TOPIC_COMMAND, json.dumps({"command": "SNAPSHOT", "device": DEVICE}))
            log(f"Button pressed -> published SNAPSHOT to {TOPIC_COMMAND}")
        else:
            while True:  # no keyboard (stdin closed): keep running until Ctrl+C
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    running = False
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
