import json
import ssl
import threading
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore", category=DeprecationWarning)

import paho.mqtt.client as mqtt

from config import (
    MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE,
    MQTT_USE_TLS, MQTT_USERNAME, MQTT_PASSWORD,
    TOPIC_DISCOVERY, TOPIC_STATE_WILDCARD, TOPIC_CMD_FMT, TOPIC_CMD_LEGACY_FMT,
    DRAIN_CRITICAL_WEIGHT, make_client_id,
)
from db import SessionLocal, Device, Reading, Alert

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _QT_AVAILABLE = True
except Exception:
    _QT_AVAILABLE = False


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


if _QT_AVAILABLE:
    class MqttBridge(QObject):
        telemetry = pyqtSignal(dict)
        connected = pyqtSignal(bool)
        error     = pyqtSignal(str)
else:
    class MqttBridge:
        pass


class MQTTService:
    def __init__(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=make_client_id("web"),
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        self.is_running           = False
        self._lock                = threading.Lock()
        self.bridge               = MqttBridge() if _QT_AVAILABLE else None

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[MQTT-web] connected as {client._client_id}")
            client.subscribe(TOPIC_DISCOVERY)
            client.subscribe(TOPIC_STATE_WILDCARD)
            if self.bridge:
                self.bridge.connected.emit(True)
        else:
            print(f"[MQTT-web] connect FAILED reason={reason_code}")
            if self.bridge:
                self.bridge.connected.emit(False)
                self.bridge.error.emit(f"MQTT connect {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[MQTT-web] disconnect reason={reason_code}")
        if self.bridge:
            self.bridge.connected.emit(False)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8")}

        db = SessionLocal()
        try:
            if msg.topic == TOPIC_DISCOVERY:
                self._handle_discovery(db, payload)
            elif msg.topic.endswith("/state"):
                self._handle_state(db, msg.topic, payload)
            elif msg.topic.endswith("/command"):
                self._handle_state(db, msg.topic.replace("/command", "/state"), payload)
        except Exception as e:
            print(f"[MQTT Ошибка]: {e}")
        finally:
            db.close()

    def _handle_discovery(self, db, payload):
        dev_id = payload.get("device_id")
        if not dev_id:
            return
        existing = db.query(Device).filter(Device.device_id == dev_id).first()
        if existing:
            existing.status    = "active"
            existing.last_seen = _utcnow()
            existing.name      = payload.get("name", existing.name)
        else:
            db.add(Device(
                device_id   = dev_id,
                name        = payload.get("name", f"Модуль {dev_id}"),
                category    = payload.get("category") or payload.get("type", "sensor"),
                subtype     = payload.get("subtype", "general"),
                mqtt_topic  = f"gh/greenhouse/{dev_id}",
                status      = "pending",
                config_json = json.dumps(payload.get("config", {})),
            ))
            db.add(Alert(
                title    = "Автообнаружение",
                severity = "info",
                message  = f"Обнаружен новый модуль [{payload.get('subtype','device')}]: {dev_id}",
            ))
        db.commit()
        if self.bridge:
            self.bridge.telemetry.emit({"action": "discovery", "device_id": dev_id})

    def _handle_state(self, db, topic, payload):
        parts = topic.split("/")
        if len(parts) < 3:
            return
        dev_id = payload.get("device_id") or parts[-2]

        device = db.query(Device).filter(Device.device_id == dev_id).first()
        if not device:
            return

        device.status    = "active"
        device.last_seen = _utcnow()

        values = payload.get("values", payload)
        if "values" in payload:
            temp  = values.get("temp_c",  values.get("temperature"))
            hum   = values.get("hum_pct", values.get("humidity"))
            light = values.get("light_lux", values.get("light"))
            soil  = values.get("soil_pct")
            if hum is None and soil is not None:
                hum = soil
        else:
            temp  = values.get("temperature")
            hum   = values.get("humidity")
            light = values.get("light")

        db.add(Reading(
            device_id       = dev_id,
            temperature     = temp,
            humidity        = hum,
            ph              = values.get("ph"),
            ec              = values.get("ec"),
            co2             = values.get("co2"),
            light           = light,
            drainage_weight = values.get("drainage_weight"),
            tank_level      = values.get("tank_level"),
            state           = values.get("state"),
        ))

        drain = values.get("drainage_weight")
        if drain is not None and drain > DRAIN_CRITICAL_WEIGHT and device.drain_serviced:
            device.drain_serviced = False
            db.add(Alert(
                title    = "Дренаж переполнен",
                severity = "danger",
                message  = f"Устройство {dev_id}: вес дренажа {drain} г",
            ))

        db.commit()
        if self.bridge:
            self.bridge.telemetry.emit({
                "action": "state", "device_id": dev_id,
                "temp": temp, "hum": hum, "payload": payload,
            })

    def start(self):
        if self.is_running:
            return
        try:
            if MQTT_USE_TLS:
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED,
                                    tls_version=ssl.PROTOCOL_TLS_CLIENT)
            if MQTT_USERNAME:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            self.client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            self.is_running = True
        except Exception as e:
            print(f"[MQTT-web] Не удалось запустить: {e}")

    def stop(self):
        if not self.is_running:
            return
        try:
            self.client.loop_stop()
            self.client.disconnect()
        finally:
            self.is_running = False

    def send_command(self, zone_name: str, device_id: str, cmd_data: dict):
        with self._lock:
            topic = TOPIC_CMD_FMT.format(zone=zone_name or "greenhouse", device_id=device_id)
            self.client.publish(topic, json.dumps(cmd_data))
            legacy = TOPIC_CMD_LEGACY_FMT.format(device_id=device_id)
            legacy_payload = {
                "command": str(cmd_data.get("action", cmd_data.get("command", "ON"))).upper()
            }
            self.client.publish(legacy, json.dumps(legacy_payload))
            print(f"[MQTT PUB] -> {topic}: {cmd_data}")


mqtt_service = MQTTService()