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
