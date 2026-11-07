from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QPushButton, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QInputDialog, QComboBox, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QBrush, QPen, QColor, QFont, QPainter

from config import UI_UPDATE_INTERVAL_MS, MAP_W, MAP_H, ZONE_W, ZONE_H
from db import (
    SessionLocal, Zone, Device, Reading, Alert,
    bump_layout_version, get_layout_version,
)
from ui.scenarios_window import ScenariosWindow
from ui.charts_window import ChartsWindow
from ui.styles import build_style

LAYOUT_POLL_INTERVAL_MS = 1000


SUBTYPE_LABELS = {
    "humidity":     "Датчик влажности",
    "temperature":  "Датчик температуры",
    "climate":      "Климат-датчик",
    "soil_sensor":  "Датчик почвы",
    "co2":          "Датчик CO₂",
    "ph":           "Датчик pH",
    "ec":           "Датчик EC",
    "water_sensor": "Датчик уровня воды",
    "light":        "Датчик освещённости",
    "pump":         "Насос",
    "fan":          "Вентилятор",
    "led_light":    "LED-освещение",
    "valve":        "Клапан",
    "general":      "Устройство",
}


def pretty_type(category: str, subtype: str) -> str:
    return SUBTYPE_LABELS.get(subtype, f"{category}/{subtype}")


def latlng_to_scene(lat: float, lng: float):
    x = lng - ZONE_W / 2
    y = MAP_H - lat - ZONE_H / 2
    return x, y


def scene_to_latlng(x: float, y: float):
    lng = x + ZONE_W / 2
    lat = MAP_H - y - ZONE_H / 2
    return lat, lng


class DraggableZone(QGraphicsRectItem):
    def __init__(self, zone: Zone, parent_window):
        super().__init__(0, 0, ZONE_W, ZONE_H)

        x, y = latlng_to_scene(zone.lat, zone.lng)
        self.setPos(x, y)

        self.zone = zone
        self.zone_id = zone.id
        self.parent_window = parent_window
        self.setBrush(QBrush(QColor("#d4efdf")))
        self.setPen(QPen(QColor("#27ae60"), 2))
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )

        self.text = QGraphicsTextItem(zone.name, self)
        self.text.setDefaultTextColor(QColor("#1e8449"))
        f = QFont(); f.setBold(True); f.setPointSize(10)
        self.text.setFont(f)
        self.text.setPos(8, 6)

        self.dev_text = QGraphicsTextItem("", self)
        self.dev_text.setDefaultTextColor(QColor("#475569"))
        f2 = QFont(); f2.setPointSize(8)
        self.dev_text.setFont(f2)
        self.dev_text.setPos(8, 30)
        self.dev_text.setTextWidth(ZONE_W - 16)

    def update_devices(self, dev_list):
        if not dev_list:
            self.dev_text.setPlainText("Нет устройств")
        else:
            self.dev_text.setPlainText(
                "Устройства:\n" + "\n".join(f"• {d}" for d in dev_list)
            )

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        pos = self.pos()
        lat, lng = scene_to_latlng(pos.x(), pos.y())

        db = SessionLocal()
        try:
            z = db.query(Zone).filter(Zone.id == self.zone.id).first()
            if z:
                if abs(z.lat - lat) > 0.01 or abs(z.lng - lng) > 0.01:
                    z.lat = lat
                    z.lng = lng
                    z.updated_at = datetime.utcnow()
                    db.commit()
                    self.zone.lat = lat
                    self.zone.lng = lng
        finally:
            db.close()

        bump_layout_version()

    def contextMenuEvent(self, event):
        menu = QMenu()
        rename = menu.addAction("Переименовать")
        delete = menu.addAction("Удалить")
        action = menu.exec(event.screenPos())

        if action == rename:
            new_name, ok = QInputDialog.getText(
                None, "Переименовать", "Новое название:", text=self.zone.name
            )
            if ok and new_name.strip():
                db = SessionLocal()
                try:
                    z = db.query(Zone).filter(Zone.id == self.zone.id).first()
                    if z:
                        z.name = new_name.strip()
                        z.updated_at = datetime.utcnow()
                        db.commit()
                finally:
                    db.close()
                bump_layout_version()
                self.parent_window.refresh_map(force=True)

        elif action == delete:
            db = SessionLocal()
            try:
                z = db.query(Zone).filter(Zone.id == self.zone.id).first()
                if z:
                    db.delete(z)
                    db.commit()
            finally:
                db.close()
            bump_layout_version()
            self.parent_window.refresh_map(force=True)


class MainWindow(QMainWindow):
    def __init__(self, mqtt_worker, rules_engine):
        super().__init__()
        self.setWindowTitle("SmartFarm")
        self.resize(1400, 900)

        self.mqtt  = mqtt_worker
        self.rules = rules_engine
        self.mqtt.telemetry.connect(self.on_telemetry)
        self.mqtt.connected.connect(self.on_mqtt_connected)
        self.mqtt.error.connect(self.on_mqtt_error)

        self._zone_items = {}
        self._layout_version = 0
        self._tick = 0

        self._settings = QSettings("SmartFarm", "Desktop")
        self._theme = self._settings.value("theme", "light", type=str)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget(objectName="Header")
        header.setFixedHeight(64)
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 0, 24, 0)
        h.addWidget(QLabel("SmartFarm", objectName="Logo"))
        h.addStretch()

        self.lbl_mqtt = QLabel("● MQTT: …")
        self.lbl_mqtt.setObjectName("MqttStatus")
        self.lbl_mqtt.setProperty("connected", "false")
        h.addWidget(self.lbl_mqtt)

        h.addSpacing(8)
        self.btn_theme = QPushButton("🌙" if self._theme != "dark" else "☀️")
        self.btn_theme.setObjectName("ThemeToggle")
        self.btn_theme.setToolTip("Переключить тему")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        h.addWidget(self.btn_theme)

        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_dashboard_tab(), "Дашборд")
        self.tabs.addTab(self.create_map_tab(),      "Карта теплицы")
        self.tabs.addTab(self.create_devices_tab(),  "Устройства")
        self.tabs.addTab(self.create_charts_tab(),   "Графики")
        self.tabs.addTab(self.create_scenarios_tab(),"Сценарии")
        root.addWidget(self.tabs)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(UI_UPDATE_INTERVAL_MS)

        self.layout_timer = QTimer(self)
        self.layout_timer.timeout.connect(self._sync_layout_from_db)
        self.layout_timer.start(LAYOUT_POLL_INTERVAL_MS)

        self._layout_version = get_layout_version()
        print(f"[INIT] layout version = {self._layout_version}, theme = {self._theme}")

        QTimer.singleShot(0, lambda: self._apply_theme(self._theme))

    def _toggle_theme(self):
        new = "dark" if self._theme != "dark" else "light"
        self._apply_theme(new)
        self._settings.setValue("theme", new)

    def _apply_theme(self, theme: str):
        self._theme = theme
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_style(theme))
        self.btn_theme.setText("☀️" if theme == "dark" else "🌙")
        self.btn_theme.setToolTip("Светлая тема" if theme == "dark" else "Тёмная тема")

        dark = theme == "dark"
        for item in self._zone_items.values():
            item.setBrush(QBrush(QColor("#0f2e1f" if dark else "#d4efdf")))
            item.setPen(QPen(QColor("#22c55e" if dark else "#27ae60"), 2))
            item.text.setDefaultTextColor(QColor("#22c55e" if dark else "#1e8449"))
            item.dev_text.setDefaultTextColor(QColor("#8ea0ba" if dark else "#475569"))

        if hasattr(self, "charts_widget"):
            try:
                self.charts_widget.apply_theme(dark)
            except Exception:
                pass

    def create_dashboard_tab(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(objectName="ContentArea")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(24)

        card = QFrame(objectName="Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.addWidget(QLabel("Мониторинг теплицы", objectName="CardTitle"))
        cl.addWidget(QLabel("Параметры секторов обновляются в реальном времени.",
                            objectName="CardSub"))
        lay.addWidget(card)

        stats = QHBoxLayout(); stats.setSpacing(16)

        z_card = QFrame(objectName="Card")
        zl = QVBoxLayout(z_card)
        zl.setContentsMargins(20, 18, 20, 18)
        zl.addWidget(QLabel("Зон всего", objectName="CardSub"))
        self.lbl_zone_count = QLabel("0")
        self.lbl_zone_count.setStyleSheet(
            "font-size: 32px; font-weight: 800; letter-spacing: -0.02em;"
        )
        zl.addWidget(self.lbl_zone_count)
        stats.addWidget(z_card)

        a_card = QFrame(objectName="Card")
        al = QVBoxLayout(a_card)
        al.setContentsMargins(20, 18, 20, 18)
        al.addWidget(QLabel("Активных устройств", objectName="CardSub"))
        self.lbl_active_count = QLabel("0")
        self.lbl_active_count.setStyleSheet(
            "font-size: 32px; font-weight: 800; letter-spacing: -0.02em;"
        )
        al.addWidget(self.lbl_active_count)
        stats.addWidget(a_card)

        al_card = QFrame(objectName="Card")
        all_l = QVBoxLayout(al_card)
        all_l.setContentsMargins(20, 18, 20, 18)
        all_l.addWidget(QLabel("Непрочитанных тревог", objectName="CardSub"))
        self.lbl_alerts_count = QLabel("0")
        self.lbl_alerts_count.setStyleSheet(
            "font-size: 32px; font-weight: 800; letter-spacing: -0.02em;"
        )
        all_l.addWidget(self.lbl_alerts_count)
        stats.addWidget(al_card)

        lay.addLayout(stats)

        zones_card = QFrame(objectName="Card")
        zc = QVBoxLayout(zones_card)
        zc.setContentsMargins(24, 24, 24, 24)
        zc.addWidget(QLabel("Состояние секторов (зон)", objectName="CardTitle"))
        self.zones_table = QTableWidget(0, 6)
        self.zones_table.setHorizontalHeaderLabels(
            ["Зона", "Устройств", "Температура (°C)", "Влажность (%)", "CO₂ (ppm)", "Бак (%)"]
        )
        self.zones_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.zones_table.verticalHeader().setVisible(False)
        self.zones_table.setShowGrid(False)
        self.zones_table.setAlternatingRowColors(True)
        self.zones_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        zc.addWidget(self.zones_table)
        lay.addWidget(zones_card)
        lay.addStretch()

        scroll.setWidget(content)
        return scroll

    def create_map_tab(self):
        content = QWidget(objectName="ContentArea")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        top = QHBoxLayout()
        btn = QPushButton("Создать новую зону")
        btn.setObjectName("PrimaryButton")
        btn.clicked.connect(self.on_add_zone)
        top.addWidget(btn)
        top.addStretch()
        lay.addLayout(top)

        map_wrap = QHBoxLayout()
        map_wrap.addStretch(1)

        self.map_view = QGraphicsView()
        self.map_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.map_view.setStyleSheet(
            "background:#fafafa;border:1px solid #e2e8f0;border-radius:12px;"
        )
        self.map_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.map_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.map_view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.map_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self.map_scene = QGraphicsScene()
        self.map_scene.setSceneRect(0, 0, MAP_W, MAP_H)
        self.map_view.setScene(self.map_scene)

        self._update_map_size()

        map_wrap.addWidget(self.map_view)
        map_wrap.addStretch(1)
        lay.addLayout(map_wrap, stretch=1)

        self.map_view.resizeEvent = self._on_map_resize

        self.refresh_map(force=True)
        return content

    def _update_map_size(self):
        screen = QApplication.primaryScreen().availableGeometry()
        side = int(min(screen.height() * 0.8, screen.width() * 0.8, 800))
        self.map_view.setFixedSize(side, side)

    def _on_map_resize(self, event):
        QGraphicsView.resizeEvent(self.map_view, event)
        if hasattr(self, "map_scene") and self.map_scene.items():
            self.map_view.fitInView(
                self.map_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def create_devices_tab(self):
        content = QWidget(objectName="ContentArea")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(30, 30, 30, 30)

        card = QFrame(objectName="Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.addWidget(QLabel("Управление устройствами", objectName="CardTitle"))
        cl.addWidget(QLabel("Устройства появляются автоматически из gh/discovery.",
                            objectName="CardSub"))

        self.dev_table = QTableWidget(0, 6)
        self.dev_table.setHorizontalHeaderLabels(
            ["ID", "Название", "Тип", "Значение", "Статус", "Зона"]
        )
        self.dev_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dev_table.verticalHeader().setVisible(False)
        self.dev_table.setShowGrid(False)
        self.dev_table.setAlternatingRowColors(True)
        self.dev_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cl.addWidget(self.dev_table)
        lay.addWidget(card)
        lay.addStretch()

        self.refresh_devices_table()
        return content

    def create_charts_tab(self):
        content = QWidget(objectName="ContentArea")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(30, 30, 30, 30)
        self.charts_widget = ChartsWindow()
        lay.addWidget(self.charts_widget)
        return content

    def create_scenarios_tab(self):
        content = QWidget(objectName="ContentArea")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(30, 30, 30, 30)
        self.scenarios_widget = ScenariosWindow()
        lay.addWidget(self.scenarios_widget)
        return content

    def on_add_zone(self):
        name, ok = QInputDialog.getText(self, "Новая зона", "Название зоны:")
        if ok and name.strip():
            db = SessionLocal()
            try:
                db.add(Zone(name=name.strip(), lat=MAP_H/2, lng=MAP_W/2,
                            updated_at=datetime.utcnow()))
                db.commit()
            finally:
                db.close()
            bump_layout_version()
            self.refresh_map(force=True)

    def refresh_map(self, force: bool = False):
        if force:
            self.map_scene.clear()
            self._zone_items.clear()

        db = SessionLocal()
        try:
            zones = db.query(Zone).all()
            for z in zones:
                devs = db.query(Device).filter(
                    Device.zone_id == z.id, Device.status == "active"
                ).all()
                dev_names = [d.name for d in devs]

                want_x, want_y = latlng_to_scene(z.lat, z.lng)

                if z.id in self._zone_items:
                    item = self._zone_items[z.id]
                    item.zone = z
                    if (abs(item.pos().x() - want_x) > 0.01 or
                        abs(item.pos().y() - want_y) > 0.01):
                        item.setPos(want_x, want_y)
                    item.text.setPlainText(z.name)
                    item.update_devices(dev_names)
                else:
                    item = DraggableZone(z, self)
                    item.update_devices(dev_names)
                    self.map_scene.addItem(item)
                    self._zone_items[z.id] = item

            alive_ids = {z.id for z in zones}
            for zid in list(self._zone_items.keys()):
                if zid not in alive_ids:
                    item = self._zone_items.pop(zid)
                    try:
                        self.map_scene.removeItem(item)
                    except Exception:
                        pass
        finally:
            db.close()

        dark = self._theme == "dark"
        for item in self._zone_items.values():
            item.setBrush(QBrush(QColor("#0f2e1f" if dark else "#d4efdf")))
            item.setPen(QPen(QColor("#22c55e" if dark else "#27ae60"), 2))
            item.text.setDefaultTextColor(QColor("#22c55e" if dark else "#1e8449"))
            item.dev_text.setDefaultTextColor(QColor("#8ea0ba" if dark else "#475569"))

        if self.map_scene.items():
            self.map_view.fitInView(
                self.map_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def _sync_layout_from_db(self):
        current = get_layout_version()
        if current != self._layout_version:
            print(f"[SYNC] layout version {self._layout_version} → {current}")
            self._layout_version = current
            if hasattr(self, "map_scene"):
                self.refresh_map(force=False)

    def refresh_devices_table(self):
        db = SessionLocal()
        try:
            devices = db.query(Device).all()
            zones = db.query(Zone).all()
            self.dev_table.setRowCount(len(devices))

            for i, d in enumerate(devices):
                self.dev_table.setItem(i, 0, QTableWidgetItem(d.device_id))
                self.dev_table.setItem(i, 1, QTableWidgetItem(d.name))
                self.dev_table.setItem(i, 2, QTableWidgetItem(pretty_type(d.category, d.subtype)))

                last = db.query(Reading).filter(Reading.device_id == d.device_id)\
                        .order_by(Reading.timestamp.desc()).first()
                val = "—"
                if last:
                    if last.tank_level is not None:    val = f"Бак: {last.tank_level:.0f}%"
                    elif last.humidity is not None:    val = f"Влажность: {last.humidity:.1f}%"
                    elif last.temperature is not None: val = f"Температура: {last.temperature:.1f}°C"
                    elif last.state is not None:       val = last.state
                self.dev_table.setItem(i, 3, QTableWidgetItem(val))

                st = QTableWidgetItem(f"● {d.status}")
                if d.status == "active":
                    st.setForeground(Qt.GlobalColor.green)
                elif d.status == "pending":
                    st.setForeground(Qt.GlobalColor.darkYellow)
                else:
                    st.setForeground(Qt.GlobalColor.gray)
                self.dev_table.setItem(i, 4, st)

                combo = QComboBox()
                combo.addItem("Не привязан", None)
                for z in zones:
                    combo.addItem(z.name, z.id)
                if d.zone_id:
                    idx = combo.findData(d.zone_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.currentIndexChanged.connect(
                    lambda _, dev_pk=d.id, c=combo: self.on_zone_change(dev_pk, c)
                )
                self.dev_table.setCellWidget(i, 5, combo)
        finally:
            db.close()

    def on_zone_change(self, dev_pk, combo):
        z_id = combo.currentData()
        db = SessionLocal()
        try:
            d = db.query(Device).filter(Device.id == dev_pk).first()
            if d:
                d.zone_id = z_id
                if d.status == "pending":
                    d.status = "active"
                d.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        bump_layout_version()
        self.refresh_map(force=False)

    def refresh_ui(self):
        db = SessionLocal()
        try:
            zones = db.query(Zone).all()
            self.lbl_zone_count.setText(str(len(zones)))
            active = db.query(Device).filter(Device.status == "active").count()
            self.lbl_active_count.setText(str(active))
            unread = db.query(Alert).filter(Alert.acknowledged == False).count()
            self.lbl_alerts_count.setText(str(unread))

            self.zones_table.setRowCount(len(zones))
            for row, z in enumerate(zones):
                devs = db.query(Device).filter(
                    Device.zone_id == z.id, Device.status == "active"
                ).all()
                t, h, c, tank = [], [], [], []
                for d in devs:
                    r = db.query(Reading).filter(Reading.device_id == d.device_id)\
                            .order_by(Reading.timestamp.desc()).first()
                    if r:
                        if r.temperature is not None: t.append(r.temperature)
                        if r.humidity is not None:    h.append(r.humidity)
                        if r.co2 is not None:         c.append(r.co2)
                        if r.tank_level is not None:  tank.append(r.tank_level)

                self.zones_table.setItem(row, 0, QTableWidgetItem(z.name))
                self.zones_table.setItem(row, 1, QTableWidgetItem(str(len(devs))))
                self.zones_table.setItem(row, 2, QTableWidgetItem(
                    f"{sum(t)/len(t):.1f}" if t else "—"))
                self.zones_table.setItem(row, 3, QTableWidgetItem(
                    f"{sum(h)/len(h):.1f}" if h else "—"))
                self.zones_table.setItem(row, 4, QTableWidgetItem(
                    f"{sum(c)/len(c):.0f}" if c else "—"))
                self.zones_table.setItem(row, 5, QTableWidgetItem(
                    f"{sum(tank)/len(tank):.0f}" if tank else "—"))
        finally:
            db.close()

        self.refresh_devices_table()
        self.charts_widget.refresh_zones()

    def on_telemetry(self, data: dict):
        if data.get("action") in ("state", "discovery"):
            QTimer.singleShot(0, self.refresh_devices_table)

    def on_mqtt_connected(self, ok: bool):
        if ok:
            self.lbl_mqtt.setText("● MQTT подключен")
            self.lbl_mqtt.setProperty("connected", "true")
        else:
            self.lbl_mqtt.setText("● MQTT отключен")
            self.lbl_mqtt.setProperty("connected", "false")
        self.lbl_mqtt.style().unpolish(self.lbl_mqtt)
        self.lbl_mqtt.style().polish(self.lbl_mqtt)

    def on_mqtt_error(self, msg: str):
        self.lbl_mqtt.setText(f"● {msg[:24]}")
        self.lbl_mqtt.setProperty("connected", "false")
        self.lbl_mqtt.style().unpolish(self.lbl_mqtt)
        self.lbl_mqtt.style().polish(self.lbl_mqtt)

    def closeEvent(self, e):
        super().closeEvent(e)