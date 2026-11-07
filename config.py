import os
import uuid
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "greenhouse_house.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID_PREFIX = "smartfarm"
MQTT_USE_TLS = False
MQTT_USERNAME = None
MQTT_PASSWORD = None
TOPIC_DISCOVERY       = "gh/discovery"
TOPIC_STATE_WILDCARD  = "gh/+/+/state"
TOPIC_STATE_FMT       = "gh/{zone}/{device_id}/state"
TOPIC_CMD_FMT         = "gh/{zone}/{device_id}/cmd"
TOPIC_CMD_LEGACY_FMT  = "gh/{device_id}/command"
UI_UPDATE_INTERVAL_MS      = 1000
CHARTS_REFRESH_INTERVAL_MS = 5000
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
DEFAULT_WATER_DURATION_SEC = 10
DRAIN_CRITICAL_WEIGHT      = 900.0
DAILY_WATER_LIMIT_ML       = 6000
MAP_W = 1000
MAP_H = 1000
ZONE_W = 160
ZONE_H = 110
LOG_LEVEL = "INFO"
LOG_FILE  = os.path.join(BASE_DIR, "smartfarm.log")
def make_client_id(role: str) -> str:
    return f"{MQTT_CLIENT_ID_PREFIX}_{role}_{uuid.uuid4().hex[:8]}"