from datetime import datetime, timedelta, timezone

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QCheckBox,
    QGridLayout, QFrame, QSizePolicy,
)
from PyQt6.QtCore import QTimer, Qt

from config import CHARTS_REFRESH_INTERVAL_MS
from db import SessionLocal, Zone, Device, Reading


PARAMS = [
    ("temperature", "Температура", "°C"),
    ("humidity",    "Влажность",   "%"),
    ("ph",          "pH",          ""),
    ("ec",          "EC",          "мСм/см"),
    ("co2",         "CO₂",         "ppm"),
    ("tank_level",  "Бак",         "%"),
]

PERIODS = [
    ("15 минут",  timedelta(minutes=15)),
    ("1 час",     timedelta(hours=1)),
    ("6 часов",   timedelta(hours=6)),
    ("24 часа",   timedelta(days=1)),
    ("7 дней",    timedelta(days=7)),
]


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


COLORS = ["#22c55e", "#ef4444", "#3b82f6", "#f59e0b", "#a855f7", "#06b6d4"]


class ChartsWindow(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        top = QHBoxLayout()

        top.addWidget(QLabel("Зона:"))
        self.zone_box = QComboBox()
        self.zone_box.setMinimumWidth(180)
        self.zone_box.currentIndexChanged.connect(self.reload)
        top.addWidget(self.zone_box)

        top.addSpacing(16)
        top.addWidget(QLabel("Период:"))
        self.period_box = QComboBox()
        for label, _ in PERIODS:
            self.period_box.addItem(label)
        self.period_box.setCurrentIndex(1)
        self.period_box.currentIndexChanged.connect(self.reload)
        top.addWidget(self.period_box)

        top.addSpacing(16)
        self.autoreload = QCheckBox("Автообновление")
        self.autoreload.setChecked(True)
        self.autoreload.stateChanged.connect(self._on_autoreload_changed)
        top.addWidget(self.autoreload)

        top.addStretch()
        root.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(8)

        self.plots = {}

        for i, (field, title, unit) in enumerate(PARAMS):
            r, c = divmod(i, 3)

            frame = QFrame(objectName="ChartCard")
            frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(8, 6, 8, 6)
            fl.setSpacing(2)

            header = QLabel(f"{title}" + (f", {unit}" if unit else ""))
            header.setStyleSheet("font-size:12px;font-weight:600;")
            fl.addWidget(header)

            plot = pg.PlotWidget(background="w")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setMouseEnabled(x=True, y=False)
            axis = pg.DateAxisItem(orientation="bottom")
            plot.setAxisItems({"bottom": axis})
            fl.addWidget(plot)

            grid.addWidget(frame, r, c)

            self.plots[field] = {
                "frame":  frame,
                "plot":   plot,
                "curves": {},
                "title":  title,
                "unit":   unit,
            }

        root.addLayout(grid, stretch=1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)
        self.timer.start(CHARTS_REFRESH_INTERVAL_MS)

        self.refresh_zones()

    def _on_autoreload_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self.timer.start(CHARTS_REFRESH_INTERVAL_MS)
        else:
            self.timer.stop()

    def refresh_zones(self):
        current_id = self.zone_box.currentData()

        self.zone_box.blockSignals(True)
        self.zone_box.clear()
        self.zone_box.addItem("— Все зоны —", None)

        db = SessionLocal()
        try:
            for z in db.query(Zone).order_by(Zone.name).all():
                self.zone_box.addItem(z.name, z.id)
        finally:
            db.close()

        if current_id is not None:
            idx = self.zone_box.findData(current_id)
            if idx >= 0:
                self.zone_box.setCurrentIndex(idx)

        self.zone_box.blockSignals(False)

        new_id = self.zone_box.currentData()
        if new_id != current_id:
            self.reload()

    def reload(self):
        zone_id = self.zone_box.currentData()
        period_idx = self.period_box.currentIndex()
        since = _utcnow() - PERIODS[period_idx][1]

        db = SessionLocal()
        try:
            dev_q = db.query(Device).filter(Device.status == "active")
            if zone_id is not None:
                dev_q = dev_q.filter(Device.zone_id == zone_id)
            devices = dev_q.all()
            device_map = {d.device_id: d for d in devices}

            if not device_map:
                for field, info in self.plots.items():
                    self._clear_plot(info)
                    info["plot"].setTitle(
                        f"{info['title']}" + (f", {info['unit']}" if info["unit"] else ""),
                        color="#94a3b8", size="9pt",
                    )
                return

            device_ids = list(device_map.keys())
            readings = db.query(Reading).filter(
                Reading.device_id.in_(device_ids),
                Reading.timestamp >= since,
            ).order_by(Reading.timestamp.asc()).all()

            buckets = {field: {dev_id: [] for dev_id in device_ids} for field, _, _ in PARAMS}

            for r in readings:
                ts = r.timestamp
                if ts is None:
                    continue
                x = ts.replace(tzinfo=timezone.utc).timestamp()
                for field, _, _ in PARAMS:
                    v = getattr(r, field, None)
                    if v is not None:
                        buckets[field][r.device_id].append((x, float(v)))
        finally:
            db.close()

        for field, info in self.plots.items():
            title = info["title"] + (f", {info['unit']}" if info["unit"] else "")
            info["plot"].setTitle(title, size="10pt")

            field_buckets = buckets.get(field, {})
            has_any = any(len(points) > 0 for points in field_buckets.values())

            if not has_any:
                self._clear_plot(info)
                info["plot"].setTitle(title + "  (нет данных)", size="9pt")
                continue

            existing_ids = set(info["curves"].keys())
            incoming_ids = {dev_id for dev_id, points in field_buckets.items() if points}

            for dev_id in existing_ids - incoming_ids:
                info["plot"].removeItem(info["curves"][dev_id])
                del info["curves"][dev_id]

            for i, dev_id in enumerate(sorted(incoming_ids)):
                points = field_buckets[dev_id]
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                color = COLORS[i % len(COLORS)]

                if dev_id in info["curves"]:
                    info["curves"][dev_id].setData(xs, ys)
                else:
                    pen = pg.mkPen(color, width=2)
                    curve = info["plot"].plot(xs, ys, pen=pen)
                    info["curves"][dev_id] = curve

            all_ys = [y for pts in field_buckets.values() for _, y in pts]
            if all_ys:
                ymin, ymax = min(all_ys), max(all_ys)
                margin = (ymax - ymin) * 0.1 if ymax > ymin else max(abs(ymax) * 0.1, 1.0)
                info["plot"].setYRange(ymin - margin, ymax + margin, padding=0)

            x_start = since.replace(tzinfo=timezone.utc).timestamp()
            x_end = _utcnow().replace(tzinfo=timezone.utc).timestamp()
            info["plot"].setXRange(x_start, x_end, padding=0)

    def _clear_plot(self, info):
        for curve in info["curves"].values():
            info["plot"].removeItem(curve)
        info["curves"].clear()

    def apply_theme(self, dark: bool):
        bg = "#111a2b" if dark else "w"
        axis_pen = pg.mkPen("#2c3b57" if dark else "#cbd5e1")
        text_pen = pg.mkPen("#e6ecf5" if dark else "#334155")

        for info in self.plots.values():
            info["plot"].setBackground(bg)
            for ax_name in ("left", "bottom"):
                ax = info["plot"].getAxis(ax_name)
                ax.setPen(axis_pen)
                ax.setTextPen(text_pen)