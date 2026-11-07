import json
import time
import random
import sys

import paho.mqtt.client as mqtt

BROKER     = "localhost"
PORT       = 1883
ZONE_NAME  = "greenhouse"
PERIOD_SEC = 3

ACTUATOR_TYPES = {"pump", "fan", "led_light", "valve"}


if len(sys.argv) < 2:
    print("Использование: python sim.py <device_id> [subtype]")
    print("Пример:        python sim.py water_tank_01 water_sensor")
    print("Пример:        python sim.py soil-01 soil_sensor")
    print("Пример:        python sim.py pump-01 pump")
    sys.exit(1)

device_id = sys.argv[1]
subtype   = sys.argv[2] if len(sys.argv) > 2 else "soil_sensor"
dev_category = "actuator" if subtype in ACTUATOR_TYPES else "sensor"


client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    print(f"[SIMULATOR] {device_id} ({subtype}) connected rc={rc}")

    discovery_payload = {
        "device_id": device_id,
        "name":      f"Эмулятор {subtype} {device_id}",
        "category":  dev_category,
        "subtype":   subtype,
        "config":    {"min_humidity": 35.0, "max_temp": 28.0},
    }
    client.publish("gh/discovery", json.dumps(discovery_payload))
    print(f"[DISC] {discovery_payload}")

    client.subscribe(f"gh/{ZONE_NAME}/{device_id}/cmd")
    client.subscribe(f"gh/{device_id}/command")


def on_message(client, userdata, msg):
    print(f"[SIMULATOR {device_id}] CMD [{msg.topic}]: {msg.payload.decode()}")
    try:
        data = json.loads(msg.payload.decode())
        if data.get("action") == "water":
            global soil_humidity, tank_level
            duration = data.get("duration", 5)
            print(f"[SIMULATOR {device_id}] полив {duration} сек.")
            soil_humidity = min(95.0, soil_humidity + duration * 2.2)
            tank_level    = max(0.0,  tank_level    - duration * 1.5)
    except Exception as e:
        print(f"[SIMULATOR] parse error: {e}")


client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

soil_humidity = 27.0
tank_level    = 75.0
temperature   = 24.5
ec            = 1.3
ph            = 6.2
co2           = 420.0
light         = 18000.0
drainage      = 80.0

try:
    while True:
        soil_humidity -= 0.15
        if soil_humidity < 10.0:
            soil_humidity = 10.0

        tank_level -= 0.05
        if tank_level < 0.0:
            tank_level = 0.0

        temperature += random.uniform(-0.1, 0.1)

        payload = {
            "device_id": device_id,
            "type":      dev_category,
            "subtype":   subtype,
            "values": {
                "temperature":     round(temperature, 2),
                "humidity":        round(soil_humidity, 1),
                "ph":              ph,
                "ec":              ec,
                "co2":             round(co2, 1),
                "light":           light,
                "drainage_weight": round(drainage, 1),
                "tank_level":      round(tank_level, 1),
            },
        }

        topic = f"gh/{ZONE_NAME}/{device_id}/state"
        client.publish(topic, json.dumps(payload))
        print(f"[TX {topic}] {payload}")

        time.sleep(PERIOD_SEC)

except KeyboardInterrupt:
    print(f"\n[SIMULATOR] {device_id} остановлен.")
    client.loop_stop()
    client.disconnect()