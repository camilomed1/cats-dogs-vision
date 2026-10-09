"""MongoDB storage: image bytes in GridFS, metadata + prediction in the `predictions` collection."""
import hashlib
from datetime import datetime, timezone

import gridfs
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, MongoClient


def to_object_id(value: str):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class Storage:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True)
        self.db = self.client[db_name]
        self.fs = gridfs.GridFSBucket(self.db, bucket_name="images")
        self.predictions = self.db["predictions"]
        self.predictions.create_index([("createdAt", DESCENDING)])

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def save(self, image_bytes: bytes, mime_type: str, metadata: dict, image_info: dict,
             prediction: dict) -> tuple[str, str]:
        """Returns (prediction id, GridFS image id)."""
        now = datetime.now(timezone.utc)
        filename = metadata.get("filename") or f"{metadata.get('client', 'unknown')}_{now:%Y%m%d_%H%M%S}"
        file_id = self.fs.upload_from_stream(
            filename,
            image_bytes,
            metadata={"contentType": mime_type, "clientMetadata": metadata, **image_info},
        )
        doc = {
            "imageFileId": file_id,
            "metadata": metadata,
            "image": {
                **image_info,
                "mimeType": mime_type,
                "sizeBytes": len(image_bytes),
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
            },
            "prediction": prediction,
            "createdAt": now,
        }
        return str(self.predictions.insert_one(doc).inserted_id), str(file_id)

    def history(self, limit: int, client: str | None = None) -> list[dict]:
        query = {"metadata.client": client} if client else {}
        cursor = self.predictions.find(query).sort("createdAt", DESCENDING).limit(limit)
        return [serialize(d) for d in cursor]

    def get(self, prediction_id: str) -> dict | None:
        oid = to_object_id(prediction_id)
        doc = self.predictions.find_one({"_id": oid}) if oid else None
        return serialize(doc) if doc else None

    def open_image(self, file_id: str):
        """Returns (bytes, content type) or None."""
        oid = to_object_id(file_id)
        if not oid:
            return None
        try:
            stream = self.fs.open_download_stream(oid)
        except gridfs.errors.NoFile:
            return None
        content_type = (stream.metadata or {}).get("contentType", "application/octet-stream")
        return stream.read(), content_type

    def delete(self, prediction_id: str) -> bool:
        oid = to_object_id(prediction_id)
        doc = self.predictions.find_one_and_delete({"_id": oid}) if oid else None
        if not doc:
            return False
        try:
            self.fs.delete(doc["imageFileId"])
        except gridfs.errors.NoFile:
            pass
        return True


def serialize(doc: dict) -> dict:
    file_id = str(doc["imageFileId"])
    return {
        "id": str(doc["_id"]),
        "imageId": file_id,
        "imageUrl": f"/api/images/{file_id}",
        "metadata": doc.get("metadata", {}),
        "image": doc.get("image", {}),
        **doc["prediction"],
        "createdAt": doc["createdAt"].isoformat(),
    }
