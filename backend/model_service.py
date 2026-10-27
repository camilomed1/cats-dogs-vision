"""Loads the trained Keras model and runs predictions on raw image bytes."""
import io
import json
import threading
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
import keras
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImageError(ValueError):
    pass


class ModelService:
    def __init__(self, model_dir: Path, uncertain_threshold: float):
        self.info = json.loads((model_dir / "model_info.json").read_text())
        self.img_size = self.info["img_size"]
        self.class_names = [c.lower() for c in self.info["class_names"]]
        self.threshold = uncertain_threshold
        self.model = keras.models.load_model(model_dir / self.info["model_file"])
        # Compiled TensorFlow graph for one image: ~9x faster than calling the model eagerly
        # (avoids Python overhead on each of the model's hundreds of layers).
        self._infer = tf.function(
            lambda x: self.model(x, training=False),
            input_signature=[tf.TensorSpec([1, self.img_size, self.img_size, 3], tf.float32)],
        )
        self._lock = threading.Lock()
        # First call builds the TF graph (slow); do it now instead of on the first request.
        self._run(np.zeros((self.img_size, self.img_size, 3), dtype=np.float32))

    @staticmethod
    def decode(image_bytes: bytes) -> tuple[Image.Image, str]:
        """Bytes -> (RGB PIL image with phone EXIF rotation applied, original format e.g. "JPEG")."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
        except (UnidentifiedImageError, OSError) as e:
            raise InvalidImageError("Could not decode image (supported: JPEG, PNG, BMP, GIF, WEBP)") from e
        return ImageOps.exif_transpose(img).convert("RGB"), img.format

    def preprocess(self, img: Image.Image) -> np.ndarray:
        # Same as training: bilinear resize, float32 in [0, 255]. Normalization is inside the model.
        return tf.image.resize(np.asarray(img), (self.img_size, self.img_size)).numpy()

    def _run(self, x: np.ndarray) -> float:
        with self._lock:
            return float(self._infer(x[np.newaxis, ...])[0, 0])

    def predict(self, img: Image.Image) -> dict:
        start = time.perf_counter()
        p_dog = self._run(self.preprocess(img))
        p_cat = 1.0 - p_dog
        predicted = self.class_names[1] if p_dog >= 0.5 else self.class_names[0]
        confidence = max(p_dog, p_cat)
        return {
            "label": predicted if confidence >= self.threshold else "uncertain",
            "predictedClass": predicted,
            "confidence": round(confidence, 4),
            "probabilities": {self.class_names[0]: round(p_cat, 4), self.class_names[1]: round(p_dog, 4)},
            "threshold": self.threshold,
            "inferenceMs": round((time.perf_counter() - start) * 1000, 1),
        }
