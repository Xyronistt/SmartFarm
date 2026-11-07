import json as _json
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    text, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool

from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=NullPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA read_uncommitted=1;")
    cur.execute("PRAGMA busy_timeout=30000;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _utcnow():
    return datetime.utcnow()


class Zone(Base):
    __tablename__ = "zones"
    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    description = Column(String, default="")
    parent_id   = Column(Integer, ForeignKey("zones.id"), nullable=True)
    lat         = Column(Float, default=500.0)
    lng         = Column(Float, default=500.0)
    updated_at  = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    devices = relationship("Device", back_populates="zone", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"
    id                 = Column(Integer, primary_key=True, index=True)
    device_id          = Column(String, unique=True, index=True, nullable=False)
    name               = Column(String, nullable=False)
    category           = Column(String, default="sensor")
    subtype            = Column(String, default="general")
    mqtt_topic         = Column(String, default="")
    status             = Column(String, default="pending")
    config_json        = Column(String, default="{}")
    zone_id            = Column(Integer, ForeignKey("zones.id"), nullable=True)
    lat                = Column(Float, default=550.0)
    lng                = Column(Float, default=550.0)
    updated_at         = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_seen          = Column(DateTime, nullable=True)
    drain_serviced     = Column(Boolean, default=True)
    daily_water_volume = Column(Float, default=0.0)

    zone     = relationship("Zone", back_populates="devices")
    readings = relationship("Reading", back_populates="device", cascade="all, delete-orphan")

    @property
    def type(self):
        return self.category

    @type.setter
    def type(self, value):
        self.category = value


class Reading(Base):
    __tablename__ = "readings"
    id              = Column(Integer, primary_key=True, index=True)
    device_id       = Column(String, ForeignKey("devices.device_id"), nullable=False)
    temperature     = Column(Float, nullable=True)
    humidity        = Column(Float, nullable=True)
    ph              = Column(Float, nullable=True)
    ec              = Column(Float, nullable=True)
    co2             = Column(Float, nullable=True)
    light           = Column(Float, nullable=True)
    drainage_weight = Column(Float, nullable=True)
    tank_level      = Column(Float, nullable=True)
    state           = Column(String, nullable=True)
    timestamp       = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="readings")


class Alert(Base):
    __tablename__ = "alerts"
    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String, default="")
    severity     = Column(String, default="info")
    message      = Column(String, nullable=False)
    acknowledged = Column(Boolean, default=False)
    timestamp    = Column(DateTime, default=datetime.utcnow)


class Scenario(Base):
    __tablename__ = "scenarios"
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String, nullable=False)
    zone_id          = Column(Integer, ForeignKey("zones.id"), nullable=True)
    condition_type   = Column(String, default="humidity")
    condition_params = Column(String, default='{"threshold": 35.0}')
    action_type      = Column(String, default="water")
    action_device_id = Column(String, default="")
    action_params    = Column(String, default='{"duration_sec": 10}')
    enabled          = Column(Boolean, default=True)

    @property
    def trigger_param(self):
        return self.condition_type

    @trigger_param.setter
    def trigger_param(self, v):
        self.condition_type = v

    @property
    def condition(self):
        return _json.loads(self.condition_params or "{}").get("op", "<")

    @condition.setter
    def condition(self, v):
        cp = _json.loads(self.condition_params or "{}")
        cp["op"] = v
        self.condition_params = _json.dumps(cp)

    @property
    def threshold_value(self):
        return float(_json.loads(self.condition_params or "{}").get("threshold", 0.0))

    @threshold_value.setter
    def threshold_value(self, v):
        cp = _json.loads(self.condition_params or "{}")
        cp["threshold"] = float(v)
        self.condition_params = _json.dumps(cp)

    @property
    def action_command(self):
        return self.action_type

    @action_command.setter
    def action_command(self, v):
        self.action_type = v

    @property
    def duration_seconds(self):
        return int(_json.loads(self.action_params or "{}").get("duration_sec", 0))

    @duration_seconds.setter
    def duration_seconds(self, v):
        ap = _json.loads(self.action_params or "{}")
        ap["duration_sec"] = int(v)
        self.action_params = _json.dumps(ap)

    @property
    def is_active(self):
        return self.enabled

    @is_active.setter
    def is_active(self, v):
        self.enabled = v


class LayoutVersion(Base):
    __tablename__ = "layout_version"
    id      = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False, default=1)


def bump_layout_version(db=None):
    own = db is None
    if own:
        db = SessionLocal()
    try:
        result = db.execute(
            text("UPDATE layout_version SET version = version + 1 WHERE id = 1")
        )
        if result.rowcount == 0:
            try:
                db.execute(text("INSERT INTO layout_version (id, version) VALUES (1, 2)"))
            except Exception:
                db.execute(text("UPDATE layout_version SET version = version + 1 WHERE id = 1"))
        db.commit()
        row = db.execute(text("SELECT version FROM layout_version WHERE id = 1")).fetchone()
        return int(row[0]) if row else 0
    finally:
        if own:
            db.close()


def get_layout_version(db=None):
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT version FROM layout_version WHERE id = 1")
            ).fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def init_db():
    Base.metadata.create_all(bind=engine)

    migrations = {
        "readings": {
            "tank_level": "FLOAT",
        },
        "zones": {
            "updated_at": "DATETIME",
        },
        "devices": {
            "updated_at": "DATETIME",
        },
    }
    with engine.begin() as conn:
        for table, cols in migrations.items():
            try:
                existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            except Exception:
                continue
            for col_name, col_type in cols.items():
                if col_name not in existing:
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                        print(f"[MIGRATION] {table}.{col_name} добавлена")
                    except Exception as e:
                        print(f"[MIGRATION] {table}.{col_name}: {e}")

    db = SessionLocal()
    try:
        if db.query(LayoutVersion).filter(LayoutVersion.id == 1).first() is None:
            db.add(LayoutVersion(id=1, version=1))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("База данных успешно инициализирована.")