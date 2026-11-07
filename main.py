from datetime import datetime, timedelta
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import WEB_HOST, WEB_PORT
from db import (
    SessionLocal, init_db, Zone, Device, Reading, Alert, Scenario,
    LayoutVersion, bump_layout_version, get_layout_version,
)
from mqtt_client import mqtt_service
from rules_engine import RulesEngine

app = FastAPI(title="SmartFarm Core")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

rules_engine = RulesEngine(interval_sec=4.0)


@app.on_event("startup")
def _startup():
    init_db()
    mqtt_service.start()
    rules_engine.start()


@app.on_event("shutdown")
def _shutdown():
    rules_engine.stop()
    mqtt_service.stop()


@app.get("/api/stats")
def api_stats():
    db = SessionLocal()
    try:
        zones_data = []
        for z in db.query(Zone).all():
            devs = db.query(Device).filter(Device.zone_id == z.id, Device.status == "active").all()
            buckets = {"temperature": [], "humidity": [], "ph": [], "co2": [], "tank_level": []}
            for d in devs:
                r = db.query(Reading).filter(Reading.device_id == d.device_id)\
                        .order_by(Reading.timestamp.desc()).first()
                if r:
                    for k in buckets:
                        v = getattr(r, k)
                        if v is not None:
                            buckets[k].append(v)
            zones_data.append({
                "zone_id":       z.id,
                "zone_name":     z.name,
                "devices_count": len(devs),
                **{k: (round(sum(v)/len(v), 1) if v else "--") for k, v in buckets.items()},
            })
        return {
            "zones_data":   zones_data,
            "alerts_count": db.query(Alert).filter(Alert.acknowledged == False).count(),
        }
    finally:
        db.close()


@app.get("/api/devices")
def api_devices():
    db = SessionLocal()
    try:
        zones_map = {z.id: z.name for z in db.query(Zone).all()}
        result = []
        for d in db.query(Device).all():
            r = db.query(Reading).filter(Reading.device_id == d.device_id)\
                    .order_by(Reading.timestamp.desc()).first()
            val = "--"
            if r:
                if r.tank_level is not None:       val = f"Бак: {r.tank_level}%"
                elif r.state is not None:          val = f"Статус: {r.state}"
                elif r.humidity is not None:       val = f"Влажность: {r.humidity}%"
                elif r.temperature is not None:    val = f"Температура: {r.temperature}°C"
                elif r.ph is not None:             val = f"pH: {r.ph}"
                elif r.co2 is not None:            val = f"CO2: {r.co2} ppm"
            result.append({
                "id": d.id, "device_id": d.device_id, "name": d.name,
                "type": d.type, "subtype": d.subtype, "status": d.status,
                "zone_id": d.zone_id,
                "zone_name": zones_map.get(d.zone_id, "Не привязана"),
                "last_value": val,
            })
        return {"devices": result}
    finally:
        db.close()


@app.get("/api/layout")
def api_layout():
    db = SessionLocal()
    try:
        zones = db.query(Zone).all()
        devices = db.query(Device).all()
        zones_payload = [
            {"id": z.id, "name": z.name, "description": z.description or "",
             "lat": z.lat, "lng": z.lng}
            for z in zones
        ]
        devices_payload = [
            {"id": d.id, "device_id": d.device_id,
             "lat": d.lat, "lng": d.lng, "zone_id": d.zone_id}
            for d in devices
        ]
    finally:
        db.close()

    version = get_layout_version()
    print(f"[LAYOUT GET] version={version}, zones={[(z['id'], round(z['lat'],1), round(z['lng'],1)) for z in zones_payload]}")
    return {
        "version": version,
        "zones":   zones_payload,
        "devices": devices_payload,
    }


@app.get("/api/charts")
def api_charts(zone_id: Optional[int] = None, period: str = "1h"):
    period_map = {
        "15m": timedelta(minutes=15),
        "1h":  timedelta(hours=1),
        "6h":  timedelta(hours=6),
        "24h": timedelta(days=1),
        "7d":  timedelta(days=7),
    }
    delta = period_map.get(period, timedelta(hours=1))
    since = datetime.utcnow() - delta

    db = SessionLocal()
    try:
        dev_q = db.query(Device).filter(Device.status == "active")
        if zone_id is not None:
            dev_q = dev_q.filter(Device.zone_id == zone_id)
        devices = dev_q.all()

        if not devices:
            return {
                "since":  since.isoformat() + "Z",
                "period": period,
                "zones":  [{"id": z.id, "name": z.name}
                           for z in db.query(Zone).order_by(Zone.name).all()],
                "devices": [],
                "series": {},
            }

        device_ids = [d.device_id for d in devices]
        readings = db.query(Reading).filter(
            Reading.device_id.in_(device_ids),
            Reading.timestamp >= since,
        ).order_by(Reading.timestamp.asc()).all()

        fields = ["temperature", "humidity", "ph", "ec", "co2", "tank_level"]
        series = {f: {dev_id: [] for dev_id in device_ids} for f in fields}

        for r in readings:
            t_iso = r.timestamp.isoformat() + "Z"
            for f in fields:
                v = getattr(r, f, None)
                if v is not None:
                    series[f][r.device_id].append({"t": t_iso, "v": float(v)})

        for f in fields:
            series[f] = {dev_id: pts for dev_id, pts in series[f].items() if pts}

        return {
            "since":  since.isoformat() + "Z",
            "period": period,
            "zones":  [{"id": z.id, "name": z.name}
                       for z in db.query(Zone).order_by(Zone.name).all()],
            "devices": [{"device_id": d.device_id, "name": d.name, "subtype": d.subtype}
                        for d in devices],
            "series": series,
        }
    finally:
        db.close()


@app.post("/devices/{device_id}/bind-ajax")
def bind_device_ajax(device_id: int, data: dict = Body(...)):
    db = SessionLocal()
    try:
        zid = data.get("zone_id")
        dev = db.query(Device).filter(Device.id == device_id).first()
        if dev:
            dev.zone_id = int(zid) if zid and str(zid).isdigit() else None
            dev.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
    bump_layout_version()
    return {"status": "ok"}


@app.post("/scenarios/add-ajax")
def add_scenario_ajax(data: dict = Body(...)):
    db = SessionLocal()
    try:
        zid = data.get("zone_id")
        sc = Scenario(
            name             = data.get("name"),
            zone_id          = int(zid) if zid and str(zid).isdigit() and int(zid) > 0 else None,
            trigger_param    = data.get("trigger_param"),
            condition        = data.get("condition"),
            threshold_value  = float(data.get("threshold_value")),
            action_device_id = data.get("action_device_id", ""),
            action_command   = data.get("action_command"),
            duration_seconds = int(data.get("duration_seconds", 0)),
            is_active        = True,
        )
        db.add(sc)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.post("/scenarios/{id}/delete-ajax")
def delete_scenario_ajax(id: int):
    db = SessionLocal()
    try:
        sc = db.query(Scenario).filter(Scenario.id == id).first()
        if sc:
            db.delete(sc)
            db.commit()
        return {"status": "ok"}
    finally:
        db.close()


def _unread():
    db = SessionLocal()
    try:
        return db.query(Alert).filter(Alert.acknowledged == False).count()
    finally:
        db.close()


@app.get("/")
def index(request: Request):
    db = SessionLocal()
    try:
        zones = db.query(Zone).all()
        zones_data = []
        for z in zones:
            devs = db.query(Device).filter(Device.zone_id == z.id, Device.status == "active").all()
            acc = {k: [] for k in ("temperature", "humidity", "ph", "ec", "co2", "drainage_weight", "tank_level")}
            for d in devs:
                r = db.query(Reading).filter(Reading.device_id == d.device_id)\
                        .order_by(Reading.timestamp.desc()).first()
                if r:
                    for k in acc:
                        v = getattr(r, k)
                        if v is not None:
                            acc[k].append(v)
            zones_data.append({
                "zone":          z,
                "devices_count": len(devs),
                **{k: (round(sum(v)/len(v), 1) if v else None) for k, v in acc.items()},
            })
        return templates.TemplateResponse("dashboard.html", {
            "request":             request,
            "zones_count":         len(zones),
            "devices_count":       db.query(Device).filter(Device.status == "active").count(),
            "pending_count":       db.query(Device).filter(Device.status == "pending").count(),
            "alerts_count":        _unread(),
            "unread_alerts_count": _unread(),
            "zones_data":          zones_data,
        })
    finally:
        db.close()


@app.get("/map/")
def greenhouse_map(request: Request):
    db = SessionLocal()
    try:
        items = []
        for d in db.query(Device).all():
            r = db.query(Reading).filter(Reading.device_id == d.device_id)\
                    .order_by(Reading.timestamp.desc()).first()
            items.append({"device": d, "reading": r})
        return templates.TemplateResponse("map.html", {
            "request": request,
            "zones": db.query(Zone).all(),
            "device_items": items,
            "unread_alerts_count": _unread(),
        })
    finally:
        db.close()


@app.post("/map/api/add-zone")
def map_add_zone(name: str = Form(...), description: str = Form("")):
    db = SessionLocal()
    try:
        db.add(Zone(name=name, description=description,
                    lat=500.0, lng=500.0, updated_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()
    bump_layout_version()
    return RedirectResponse(url="/map/", status_code=303)


@app.post("/map/api/update-coords")
async def update_coords(data: dict = Body(...)):
    print(f"[COORDS-IN] {data}")
    db = SessionLocal()
    changed = False
    try:
        now = datetime.utcnow()
        if data.get("type") == "zone":
            z_id = int(data["id"]) if data.get("id") is not None else None
            z = db.query(Zone).filter(Zone.id == z_id).first()
            print(f"[COORDS] zone_id={z_id}, found={z is not None}")
            if z:
                old = (z.lat, z.lng)
                z.lat = float(data["lat"])
                z.lng = float(data["lng"])
                z.updated_at = now
                print(f"[COORDS] {old} -> ({z.lat}, {z.lng})")
                changed = True
        elif data.get("type") == "device":
            d = db.query(Device).filter(Device.id == data["id"]).first()
            if d:
                d.lat = float(data["lat"])
                d.lng = float(data["lng"])
                d.updated_at = now
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()

    if changed:
        new_version = bump_layout_version()
        print(f"[BUMP] layout version -> {new_version}")

    return {"status": "ok"}


@app.get("/zones/")
def list_zones(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse("zones.html", {
            "request": request, "zones": db.query(Zone).all(),
            "unread_alerts_count": _unread(),
        })
    finally:
        db.close()


@app.post("/zones/add")
def add_zone(name: str = Form(...), description: str = Form(""),
             parent_id: Optional[str] = Form(None)):
    db = SessionLocal()
    try:
        pid = int(parent_id) if parent_id and parent_id.isdigit() and int(parent_id) > 0 else None
        db.add(Zone(name=name, description=description, parent_id=pid,
                    lat=500.0, lng=500.0, updated_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()
    bump_layout_version()
    return RedirectResponse(url="/zones", status_code=303)


@app.post("/zones/{id}/edit")
def edit_zone(id: int, name: str = Form(...), description: str = Form(""),
              parent_id: Optional[str] = Form(None)):
    db = SessionLocal()
    try:
        z = db.query(Zone).filter(Zone.id == id).first()
        if z:
            z.name = name
            z.description = description
            z.parent_id = int(parent_id) if parent_id and parent_id.isdigit() and int(parent_id) > 0 else None
            z.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
    bump_layout_version()
    return RedirectResponse(url="/zones", status_code=303)


@app.post("/zones/{id}/delete")
def delete_zone(id: int):
    db = SessionLocal()
    try:
        z = db.query(Zone).filter(Zone.id == id).first()
        if z:
            db.delete(z)
            db.commit()
    finally:
        db.close()
    bump_layout_version()
    return RedirectResponse(url="/zones", status_code=303)


@app.get("/devices/")
def list_devices(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse("devices.html", {
            "request": request,
            "devices": db.query(Device).all(),
            "zones": db.query(Zone).all(),
            "unread_alerts_count": _unread(),
        })
    finally:
        db.close()


@app.get("/charts")
def charts_page(request: Request):
    db = SessionLocal()
    try:
        zones = db.query(Zone).order_by(Zone.name).all()
        return templates.TemplateResponse("charts.html", {
            "request": request,
            "zones": zones,
            "unread_alerts_count": _unread(),
        })
    finally:
        db.close()


@app.get("/scenarios")
def list_scenarios(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse("scenarios.html", {
            "request": request,
            "scenarios": db.query(Scenario).all(),
            "zones": db.query(Zone).all(),
            "devices": db.query(Device).filter(Device.category == "actuator").all(),
            "unread_alerts_count": _unread(),
        })
    finally:
        db.close()


@app.get("/alerts/")
def list_alerts(request: Request):
    db = SessionLocal()
    try:
        alerts = db.query(Alert).order_by(Alert.timestamp.desc()).all()
        for a in alerts:
            a.acknowledged = True
        db.commit()
        return templates.TemplateResponse("alerts.html", {
            "request": request, "alerts": alerts, "unread_alerts_count": 0,
        })
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=WEB_PORT, reload=False)