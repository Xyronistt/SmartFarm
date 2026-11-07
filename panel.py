import json

import paho.mqtt.client as mqtt
import tkinter as tk
from tkinter import ttk

MQTT_BROKER = "localhost"
MQTT_PORT   = 1883
ZONE_NAME   = "greenhouse"


class SimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Device Simulator")
        self.root.geometry("420x620")
        self.root.config(bg="#f8f9fa")

        tk.Label(root, text="Эмулятор устройства",
                 font=("Segoe UI", 11, "bold"),
                 bg="#f8f9fa", fg="#2c3e50").pack(pady=10)
        frame_info = tk.LabelFrame(root, text=" 1. Идентификация устройства ",
                                   font=("Segoe UI", 10, "bold"),
                                   bg="#f8f9fa", padx=10, pady=10)
        frame_info.pack(fill="x", padx=15, pady=5)

        tk.Label(frame_info, text="ID устройства (напр. pump_1):",
                 bg="#f8f9fa", font=("Segoe UI", 9)).pack(anchor="w")
        self.ent_id = tk.Entry(frame_info, font=("Segoe UI", 10))
        self.ent_id.insert(0, "pump_1")
        self.ent_id.pack(fill="x", pady=3)
        self.ent_id.bind("<FocusOut>", self.resubscribe_mqtt)

        tk.Label(frame_info, text="Название:",
                 bg="#f8f9fa", font=("Segoe UI", 9)).pack(anchor="w")
        self.ent_name = tk.Entry(frame_info, font=("Segoe UI", 10))
        self.ent_name.insert(0, "Помпа полива №1")
        self.ent_name.pack(fill="x", pady=3)

        # ---------- Тип и параметр ----------
        frame_type = tk.LabelFrame(root, text=" 2. Тип устройства и параметр ",
                                   font=("Segoe UI", 10, "bold"),
                                   bg="#f8f9fa", padx=10, pady=10)
        frame_type.pack(fill="x", padx=15, pady=5)

        self.param_options = [
            ("Датчик влажности (%)",      "humidity",    0,    100, 35.0,  1.0),
            ("Датчик температуры (°C)",   "temperature", -10,  50,  24.0,  0.1),
            ("Датчик pH",                 "ph",          0,    14,  6.2,   0.1),
            ("Датчик CO2 (ppm)",          "co2",         300,  2000, 450,  10.0),
            ("Датчик уровня бака (%)",    "tank_level",  0,    100, 50.0,  1.0),
            ("Исполнительный механизм",   "state",       0,    1,   "OFF", 1),
        ]
        self.combo_param = ttk.Combobox(
            frame_type,
            values=[item[0] for item in self.param_options],
            state="readonly", font=("Segoe UI", 10),
        )
        self.combo_param.current(0)
        self.combo_param.pack(fill="x", pady=3)
        self.combo_param.bind("<<ComboboxSelected>>", self.update_value_ui)

        self.frame_val = tk.LabelFrame(root, text=" 3. Значение / Статус ",
                                       font=("Segoe UI", 10, "bold"),
                                       bg="#f8f9fa", padx=10, pady=10)
        self.frame_val.pack(fill="x", padx=15, pady=5)
        self.create_value_input()

        frame_status = tk.LabelFrame(root, text=" Связь с сервером ",
                                     font=("Segoe UI", 10, "bold"),
                                     bg="#f8f9fa", padx=10, pady=10)
        frame_status.pack(fill="x", padx=15, pady=5)

        self.lbl_status = tk.Label(frame_status, text="Ожидание команд...",
                                   font=("Segoe UI", 10, "bold"),
                                   fg="#7f8c8d", bg="#f8f9fa",
                                   wraplength=350, justify="left")
        self.lbl_status.pack(anchor="w")

        btn_send = tk.Button(root, text="Отправить данные в MQTT",
                             bg="#27ae60", fg="white",
                             font=("Segoe UI", 11, "bold"), pady=6,
                             command=self.send_data)
        btn_send.pack(fill="x", padx=15, pady=15)

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connect_mqtt()

    def connect_mqtt(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            print("[MQTT] Симулятор подключен.")
        except Exception as e:
            print(f"[MQTT Ошибка]: {e}")

    def on_connect(self, client, userdata, flags, rc):
        dev_id = self.ent_id.get().strip()
        if dev_id:
            client.subscribe(f"gh/{dev_id}/command")
            client.subscribe(f"gh/{ZONE_NAME}/{dev_id}/cmd")

    def resubscribe_mqtt(self, event=None):
        try:
            dev_id = self.ent_id.get().strip()
            if dev_id:
                self.client.subscribe(f"gh/{dev_id}/command")
                self.client.subscribe(f"gh/{ZONE_NAME}/{dev_id}/cmd")
        except Exception as e:
            print("Ошибка подписки:", e)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            cmd = payload.get("command") or payload.get("action")
            self.lbl_status.config(text=f"Получена команда: {cmd}", fg="#27ae60")
            if hasattr(self, "state_var") and cmd in ("ON", "OFF"):
                self.state_var.set(cmd)
        except Exception as e:
            print("Ошибка обработки команды:", e)

    def update_value_ui(self, event=None):
        for w in self.frame_val.winfo_children():
            w.destroy()
        self.create_value_input()

    def create_value_input(self):
        idx = self.combo_param.current()
        opt = self.param_options[idx]

        if opt[1] == "state":
            tk.Label(self.frame_val, text="Состояние реле:", bg="#f8f9fa").pack(anchor="w")
            self.state_var = tk.StringVar(value="OFF")
            tk.Radiobutton(self.frame_val, text="Включено (ON)",
                           variable=self.state_var, value="ON",
                           bg="#f8f9fa").pack(anchor="w")
            tk.Radiobutton(self.frame_val, text="Выключено (OFF)",
                           variable=self.state_var, value="OFF",
                           bg="#f8f9fa").pack(anchor="w")
        else:
            tk.Label(self.frame_val, text=f"Значение ({opt[0]}):",
                     bg="#f8f9fa").pack(anchor="w")
            self.scale_val = tk.Scale(self.frame_val, from_=opt[2], to=opt[3],
                                      resolution=opt[5], orient="horizontal",
                                      bg="#f8f9fa")
            self.scale_val.set(opt[4])
            self.scale_val.pack(fill="x", pady=2)

    def send_data(self):
        dev_id   = self.ent_id.get().strip()
        dev_name = self.ent_name.get().strip()
        idx      = self.combo_param.current()
        opt      = self.param_options[idx]
        param_key = opt[1]

        if not dev_id:
            self.lbl_status.config(text="Введите ID устройства", fg="#e74c3c")
            return

        dev_category = "actuator" if param_key == "state" else "sensor"
        dev_subtype  = param_key

        disc_payload = {
            "device_id": dev_id,
            "name":      dev_name,
            "category":  dev_category,
            "subtype":   dev_subtype,
        }
        self.client.publish("gh/discovery", json.dumps(disc_payload))
        print(f"[DISC] {disc_payload}")

        values = {
            "temperature":     None,
            "humidity":        None,
            "ph":              None,
            "ec":              None,
            "co2":             None,
            "drainage_weight": None,
            "tank_level":      None,
            "state":           None,
        }

        if param_key == "state":
            values["state"] = self.state_var.get()
        else:
            values[param_key] = self.scale_val.get()

        state_payload = {
            "device_id": dev_id,
            "type":      dev_category,
            "subtype":   dev_subtype,
            "values":    values,
        }

        topic = f"gh/{ZONE_NAME}/{dev_id}/state"
        self.client.publish(topic, json.dumps(state_payload))
        print(f"[TX {topic}] {state_payload}")

        shown = {k: v for k, v in values.items() if v is not None}
        self.lbl_status.config(
            text=f"Отправлено на {topic}:\n{shown}",
            fg="#2980b9",
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorApp(root)
    root.mainloop()