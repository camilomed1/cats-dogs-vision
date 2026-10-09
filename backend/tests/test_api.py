"""End-to-end API tests: real model + real local MongoDB (a throwaway test database).

Test images are cropped from the notebook's test_predictions.png figure (held-out test images).
Run with:  .venv\\Scripts\\python -m pytest -q
"""
import base64
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from app import create_app  # noqa: E402
from model_service import ModelService  # noqa: E402
from storage import Storage  # noqa: E402

FIGURE = config.MODEL_DIR / "figures" / "test_predictions.png"
TEST_DB = "cats_dogs_vision_test"

# (left, top) of 226px tiles in the 3x4 grid that the model got right with >= 99.8%
TILES = {"cat": [(10, 110), (576, 654)], "dog": [(576, 110), (859, 110)]}


def tile_b64(left, top, fmt="JPEG"):
    img = Image.open(FIGURE).convert("RGB").crop((left + 4, top + 4, left + 222, top + 222))
    buf = io.BytesIO()
    img.save(buf, fmt)
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="session")
def storage():
    s = Storage(config.MONGO_URI, TEST_DB)
    if not s.ping():
        pytest.skip("MongoDB is not running")
    yield s
    s.client.drop_database(TEST_DB)


@pytest.fixture(scope="session")
def client(storage):
    model = ModelService(config.MODEL_DIR, config.UNCERTAIN_THRESHOLD)
    return create_app(model, storage).test_client()


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["model"]["img_size"] == 160


@pytest.mark.parametrize("expected", ["cat", "dog"])
def test_predicts_real_images(client, expected):
    for left, top in TILES[expected]:
        r = client.post("/api/predict", json={
            "image": tile_b64(left, top),
            "metadata": {"client": "web", "source": "file", "filename": f"{expected}.jpg"},
            "store": False,
        })
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["label"] == expected
        assert body["confidence"] > 0.9
        assert body["id"] is None


def test_store_history_image_delete_roundtrip(client):
    b64 = tile_b64(*TILES["dog"][0], fmt="PNG")
    r = client.post("/api/predict", json={
        "image": "data:image/png;base64," + b64,   # data URL prefix is accepted
        "metadata": {"client": "desktop", "source": "webcam", "capturedAt": "2026-10-09T12:00:00Z"},
    })
    body = r.get_json()
    assert r.status_code == 200 and body["id"] and body.get("storageError") is None

    history = client.get("/api/history?client=desktop").get_json()
    assert history[0]["id"] == body["id"]
    assert history[0]["label"] == "dog"
    assert history[0]["metadata"]["source"] == "webcam"
    assert history[0]["image"]["mimeType"] == "image/png"

    img = client.get(body["imageUrl"])
    assert img.status_code == 200 and img.mimetype == "image/png"
    assert img.data == base64.b64decode(b64)  # exact bytes back from GridFS

    assert client.delete(f"/api/predictions/{body['id']}").status_code == 200
    assert client.get(f"/api/predictions/{body['id']}").status_code == 404
    assert client.get(body["imageUrl"]).status_code == 404


def test_exif_rotation_is_applied(client):
    # A dog photo saved sideways with an EXIF "rotate 90" tag, like phones do.
    img = Image.open(io.BytesIO(base64.b64decode(tile_b64(*TILES["dog"][1])))).rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    r = client.post("/api/predict", json={"image": base64.b64encode(buf.getvalue()).decode(), "store": False})
    assert r.get_json()["label"] == "dog"


@pytest.mark.parametrize("payload, message", [
    (None, "Body must be JSON"),
    ({}, "non-empty base64"),
    ({"image": "not base64!!"}, "not valid base64"),
    ({"image": base64.b64encode(b"hello").decode()}, "Could not decode image"),
    ({"image": "aGVsbG8=", "metadata": "x"}, "must be a JSON object"),
    ({"image": "aGVsbG8=", "metadata": {"source": "fax"}}, "metadata.source"),
])
def test_bad_requests(client, payload, message):
    r = client.post("/api/predict", json=payload) if payload is not None else client.post("/api/predict", data="x")
    assert r.status_code == 400
    assert message in r.get_json()["error"]


def test_not_found(client):
    assert client.get("/api/predictions/nope").status_code == 404
    assert client.get("/api/images/000000000000000000000000").status_code == 404
