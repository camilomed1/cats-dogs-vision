import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR.parent / "training" / "export"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "cats_dogs_vision")

# Below this confidence the API answers "uncertain" instead of cat/dog.
UNCERTAIN_THRESHOLD = float(os.getenv("UNCERTAIN_THRESHOLD", "0.80"))

MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "15"))

HOST = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 so the phone can reach it over Wi-Fi
PORT = int(os.getenv("PORT", "5000"))

# MQTT: every stored prediction is published to MQTT_PREFIX/prediction (see mqtt_publisher.py).
# broker.emqx.io is public: anyone who knows the prefix can read the messages, so only small JSON
# (label, confidence, ids) is sent, never images. Use MQTT_HOST=localhost for a local Mosquitto.
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "true").lower() == "true"
MQTT_HOST = os.getenv("MQTT_HOST", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_PREFIX = os.getenv("MQTT_PREFIX", "catsdogs-vision/camilomed1")
# "tcp" (port 1883) or "websockets" (port 8083 on broker.emqx.io): use websockets if a network blocks port 1883.
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp")
