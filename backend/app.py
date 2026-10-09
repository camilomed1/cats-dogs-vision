"""Flask REST API for the cats vs dogs classifier.

Every client sends the image as a base64 string plus metadata (JSON).
Images are stored in MongoDB GridFS; predictions + metadata in the `predictions` collection.
"""
import base64
import binascii
import logging
import re

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

import config
from model_service import InvalidImageError, ModelService
from storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("api")

KNOWN_CLIENTS = {"mobile", "web", "desktop"}
KNOWN_SOURCES = {"camera", "gallery", "file", "webcam"}
PIL_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "BMP": "image/bmp", "GIF": "image/gif", "WEBP": "image/webp"}
DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,")


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def decode_base64_image(value) -> bytes:
    if not isinstance(value, str) or not value:
        raise ApiError("'image' must be a non-empty base64 string")
    value = DATA_URL_RE.sub("", value, count=1)  # accept "data:image/jpeg;base64,..." too
    value = "".join(value.split())               # some clients insert line breaks
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError("'image' is not valid base64")


def clean_metadata(value) -> dict:
    if value is None:
        return {"client": "unknown"}
    if not isinstance(value, dict):
        raise ApiError("'metadata' must be a JSON object")
    metadata = dict(value)
    if metadata.get("client") not in KNOWN_CLIENTS:
        metadata["client"] = "unknown"
    if "source" in metadata and metadata["source"] not in KNOWN_SOURCES:
        raise ApiError(f"'metadata.source' must be one of {sorted(KNOWN_SOURCES)}")
    return metadata


def create_app(model: ModelService, storage: Storage) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_IMAGE_MB * 1024 * 1024 * 4 // 3 + 64 * 1024  # base64 overhead
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error=f"Image too large (max {config.MAX_IMAGE_MB} MB)"), 413

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", database=storage.ping(), threshold=model.threshold, model=model.info)

    @app.post("/api/predict")
    def predict():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ApiError("Body must be JSON: {image: <base64>, metadata: {...}}")

        image_bytes = decode_base64_image(body.get("image"))
        metadata = clean_metadata(body.get("metadata"))
        store = body.get("store", True) is not False

        try:
            img, fmt = model.decode(image_bytes)
        except InvalidImageError as e:
            raise ApiError(str(e))

        prediction = model.predict(img)
        result = {"id": None, **prediction}

        if store:
            mime = PIL_TO_MIME.get(fmt) or metadata.get("mimeType") or "application/octet-stream"
            image_info = {"width": img.width, "height": img.height, "format": fmt}
            try:
                result["id"], image_id = storage.save(image_bytes, mime, metadata, image_info, prediction)
                result["imageUrl"] = f"/api/images/{image_id}"
            except Exception as e:  # prediction still works if MongoDB is down
                log.exception("Could not store prediction")
                result["storageError"] = str(e)

        log.info("predict client=%s source=%s -> %s (%.3f) stored=%s",
                 metadata.get("client"), metadata.get("source"), result["label"], result["confidence"], bool(result["id"]))
        return jsonify(result)

    @app.get("/api/history")
    def history():
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
        return jsonify(storage.history(limit, request.args.get("client")))

    @app.get("/api/predictions/<prediction_id>")
    def get_prediction(prediction_id):
        doc = storage.get(prediction_id)
        if not doc:
            raise ApiError("Prediction not found", 404)
        return jsonify(doc)

    @app.delete("/api/predictions/<prediction_id>")
    def delete_prediction(prediction_id):
        if not storage.delete(prediction_id):
            raise ApiError("Prediction not found", 404)
        return jsonify(deleted=prediction_id)

    @app.get("/api/images/<file_id>")
    def get_image(file_id):
        found = storage.open_image(file_id)
        if not found:
            raise ApiError("Image not found", 404)
        data, content_type = found
        return Response(data, mimetype=content_type, headers={"Cache-Control": "public, max-age=86400"})

    return app


if __name__ == "__main__":
    log.info("Loading model from %s ...", config.MODEL_DIR)
    app = create_app(ModelService(config.MODEL_DIR, config.UNCERTAIN_THRESHOLD),
                     Storage(config.MONGO_URI, config.MONGO_DB))
    app.run(host=config.HOST, port=config.PORT, threaded=True)
