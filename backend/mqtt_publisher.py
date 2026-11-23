"""Publishes every stored prediction to an MQTT broker, so IoT devices (the ESP32) can react to them.

Topics (PREFIX comes from config.MQTT_PREFIX):
    PREFIX/prediction       {"id", "label", "confidence", "client", "source", "mode", "at"}   (one per stored prediction)
    PREFIX/backend/status   "online" / "offline"   (retained; "offline" is the Last Will if the backend dies)

If the broker cannot be reached, predictions keep working: MQTT is only an extra notification.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

log = logging.getLogger("mqtt")


class MqttPublisher:
    def __init__(self, host: str, port: int, prefix: str, enabled: bool = True, transport: str = "tcp"):
        self.host, self.port, self.prefix, self.enabled = host, port, prefix.rstrip("/"), enabled
        self.connected = False
        if not enabled:
            return
        self.transport = transport
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"catsdogs-backend-{uuid.uuid4().hex[:8]}",
                                  transport=transport)
        if transport == "websockets":
            self.client.ws_set_options(path="/mqtt")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        # Last Will: the broker publishes this by itself if the backend disconnects without saying goodbye.
        self.client.will_set(f"{self.prefix}/backend/status", "offline", retain=True)
        self.client.connect_async(host, port, keepalive=30)  # connects (and reconnects) in the background
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if self.connected:
            log.info("MQTT connected to %s:%s, publishing on %s/prediction", self.host, self.port, self.prefix)
            client.publish(f"{self.prefix}/backend/status", "online", retain=True)
        else:
            log.warning("MQTT connection refused: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        log.warning("MQTT disconnected (%s); paho will retry", reason_code)

    def publish_prediction(self, prediction_id: str, prediction: dict, metadata: dict) -> bool:
        if not self.enabled or not self.connected:
            return False
        # Short payload: the ESP32's MQTT library has a small default buffer.
        payload = {
            "id": prediction_id,
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "client": metadata.get("client"),
            "source": metadata.get("source"),
            "mode": metadata.get("mode"),
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.client.publish(f"{self.prefix}/prediction", json.dumps(payload, separators=(",", ":")))
        return True

    def status(self) -> dict:
        return {"enabled": self.enabled, "connected": self.connected, "broker": f"{self.host}:{self.port}",
                "transport": getattr(self, "transport", None), "prefix": self.prefix}

    def close(self):
        if self.enabled:
            self.client.publish(f"{self.prefix}/backend/status", "offline", retain=True)
            self.client.loop_stop()
            self.client.disconnect()
