import json
import threading
import time

from db import SessionLocal, Device, Reading, Scenario, Alert
from mqtt_client import mqtt_service
from config import DAILY_WATER_LIMIT_ML


class RulesEngine:
    def __init__(self, interval_sec: float = 4.0, on_fired=None):
        self.interval = interval_sec
        self.on_fired = on_fired
        self._stop    = threading.Event()
        self._thread  = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                print(f"[Rules Engine] {e}")
            self._stop.wait(self.interval)

    def tick(self):
        db = SessionLocal()
        try:
            scenarios = db.query(Scenario).filter(Scenario.enabled == True).all()
            for sc in scenarios:
                if not sc.zone_id:
                    continue
                devices = db.query(Device).filter(
                    Device.zone_id == sc.zone_id,
                    Device.status == "active",
                ).all()
                for dev in devices:
                    self._evaluate(db, sc, dev)
        finally:
            db.close()

    def _evaluate(self, db, sc, dev):
        if sc.action_type == "water":
            if not dev.drain_serviced:
                return
            if dev.daily_water_volume >= DAILY_WATER_LIMIT_ML:
                return

        latest = db.query(Reading).filter(
            Reading.device_id == dev.device_id
        ).order_by(Reading.timestamp.desc()).first()
        if not latest:
            return

        cp = json.loads(sc.condition_params or "{}")
        ap = json.loads(sc.action_params or "{}")
        thr = float(cp.get("threshold", 35.0))
        op  = cp.get("op", "<")

        val = {
            "humidity":    latest.humidity,
            "temperature": latest.temperature,
            "ph":          latest.ph,
            "co2":         latest.co2,
            "tank_level":  latest.tank_level,
        }.get(sc.condition_type)

        if val is None:
            return

        triggered = (val < thr) if op == "<" else (val > thr) if op == ">" else False
        if not triggered:
            return

        zone_name = dev.zone.name if dev.zone else "greenhouse"
        target_id = sc.action_device_id or dev.device_id

        if sc.action_type == "water":
            duration = int(ap.get("duration_sec", 10))
            mqtt_service.send_command(zone_name, target_id,
                                      {"action": "water", "duration": duration})
            dev.daily_water_volume += duration * 10.0
            db.commit()
            self._notify(db, sc, f"water {duration}s → {target_id}", val)
            threading.Thread(
                target=self._timed_off_and_boost,
                args=(target_id, sc.zone_id, duration),
                daemon=True,
            ).start()

        elif sc.action_type == "toggle_fan":
            mqtt_service.send_command(zone_name, target_id, {"action": "toggle_fan"})
            self._notify(db, sc, f"toggle_fan → {target_id}", val)

        elif sc.action_type == "toggle_light":
            mqtt_service.send_command(zone_name, target_id, {"action": "toggle_light"})
            self._notify(db, sc, f"toggle_light → {target_id}", val)

        elif sc.action_type in ("ON", "OFF"):
            mqtt_service.send_command(zone_name, target_id, {"command": sc.action_type})
            dur = int(ap.get("duration_sec", 0))
            if sc.action_type == "ON" and dur > 0:
                threading.Thread(
                    target=self._timed_off_and_boost,
                    args=(target_id, sc.zone_id, dur),
                    daemon=True,
                ).start()
            self._notify(db, sc, f"{sc.action_type} → {target_id}", val)

    def _notify(self, db, sc, action_msg, param_val):
        msg = (f"Сценарий '{sc.name}' сработал: "
               f"{sc.condition_type}={param_val} {sc.condition} {sc.threshold_value}. "
               f"Действие: {action_msg}")
        db.add(Alert(title="Сценарий", severity="warning", message=msg))
        db.commit()
        if self.on_fired:
            try:
                self.on_fired(msg)
            except Exception:
                pass

    def _timed_off_and_boost(self, device_id: str, zone_id, duration: int):
        time.sleep(max(1, duration))
        db = SessionLocal()
        try:
            mqtt_service.send_command("greenhouse", device_id, {"command": "OFF"})
            if zone_id:
                sensors = db.query(Device).filter(
                    Device.zone_id == zone_id,
                    Device.category == "sensor",
                    Device.subtype == "humidity",
                ).all()
                for s in sensors:
                    last = db.query(Reading).filter(
                        Reading.device_id == s.device_id
                    ).order_by(Reading.timestamp.desc()).first()
                    cur = last.humidity if last and last.humidity is not None else 30.0
                    db.add(Reading(
                        device_id   = s.device_id,
                        humidity    = min(100.0, cur + 15.0),
                        temperature = last.temperature if last else None,
                    ))
                db.commit()
        finally:
            db.close()