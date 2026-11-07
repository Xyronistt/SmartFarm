import logging
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

import paho.mqtt.client as mqtt
import json
from datetime import datetime, timezone

from config import (
    LOG_LEVEL, LOG_FILE,
    MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE,
    MQTT_USE_TLS, MQTT_USERNAME, MQTT_PASSWORD,
    TOPIC_DISCOVERY, TOPIC_STATE_WILDCARD, TOPIC_CMD_FMT,
    DRAIN_CRITICAL_WEIGHT, make_client_id,
)
from db import (
    init_db, SessionLocal, Device, Reading, Alert,
    bump_layout_version, get_layout_version,
)
from rules_engine import RulesEngine
from ui.main_window import MainWindow


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MqttWorker(QThread):
    telemetry = pyqtSignal(dict)
    connected = pyqtSignal(bool)
    error     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=make_client_id("desktop"),
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[MQTT-desktop] connected as {client._client_id}")
            client.subscribe(TOPIC_DISCOVERY)
            client.subscribe(TOPIC_STATE_WILDCARD)
            self.connected.emit(True)
        else:
            print(f"[MQTT-desktop] connect FAILED reason={reason_code}")
            self.connected.emit(False)
            self.error.emit(f"MQTT connect {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[MQTT-desktop] disconnect reason={reason_code}")
        self.connected.emit(False)

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
        except Exception as e:
            print(f"[MQTT-desktop msg] {e}")
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
        self.telemetry.emit({"action": "discovery", "device_id": dev_id})

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
        self.telemetry.emit({
            "action": "state", "device_id": dev_id,
            "temp": temp, "hum": hum, "payload": payload,
        })

    def run(self):
        try:
            if MQTT_USE_TLS:
                import ssl
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED,
                                    tls_version=ssl.PROTOCOL_TLS_CLIENT)
            if MQTT_USERNAME:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            self.client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_forever()
        except Exception as e:
            print(f"[MQTT-desktop] {e}")
            self.error.emit(str(e))

    def stop(self):
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.quit()

    def send_command(self, zone_name: str, device_id: str, cmd_data: dict):
        topic = TOPIC_CMD_FMT.format(zone=zone_name or "greenhouse", device_id=device_id)
        self.client.publish(topic, json.dumps(cmd_data))


def main():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )
    init_db()

    app = QApplication(sys.argv)

    worker = MqttWorker()

    def _log_rule(msg):
        print(f"[RULE] {msg}")

    rules = RulesEngine(interval_sec=4.0, on_fired=_log_rule)

    w = MainWindow(mqtt_worker=worker, rules_engine=rules)
    worker.start()
    rules.start()
    w.show()

    code = app.exec()
    rules.stop()
    worker.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()