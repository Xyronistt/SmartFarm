import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QLabel, QHeaderView,
)
from PyQt6.QtCore import Qt

from config import DEFAULT_WATER_DURATION_SEC
from db import SessionLocal, Scenario, Zone, Device


class ScenarioDialog(QDialog):
    def __init__(self, parent=None, scenario: Scenario = None):
        super().__init__(parent)
        self.setWindowTitle("Сценарий")
        self.resize(440, 380)
        self.scenario = scenario

        form = QFormLayout(self)
        self.name_edit = QLineEdit(scenario.name if scenario else "Новый сценарий")

        self.zone_combo = QComboBox()
        db = SessionLocal()
        try:
            for z in db.query(Zone).all():
                self.zone_combo.addItem(z.name, z.id)
        finally:
            db.close()

        self.cond_combo = QComboBox()
        self.cond_combo.addItems(["humidity", "temperature", "ph", "co2", "tank_level"])

        self.op_combo = QComboBox()
        self.op_combo.addItems(["<", ">"])

        self.act_combo = QComboBox()
        self.act_combo.addItems(["water", "toggle_fan", "toggle_light", "ON", "OFF"])

        # Только исполнительные механизмы могут быть целью сценария
        self.target_combo = QComboBox()
        db = SessionLocal()
        try:
            actuators = db.query(Device).filter(Device.category == "actuator").all()
            for d in actuators:
                self.target_combo.addItem(f"{d.name} ({d.device_id})", d.device_id)
            if not actuators:
                self.target_combo.addItem("— Нет исполнительных устройств —", "")
        finally:
            db.close()

        self.thresh_edit = QLineEdit()
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(0, 600)
        self.dur_spin.setSuffix(" сек")

        if scenario:
            idx = self.zone_combo.findData(scenario.zone_id)
            if idx >= 0:
                self.zone_combo.setCurrentIndex(idx)
            self.cond_combo.setCurrentText(scenario.condition_type)
            self.op_combo.setCurrentText(scenario.condition)
            self.thresh_edit.setText(str(scenario.threshold_value))
            self.act_combo.setCurrentText(scenario.action_type)
            idx = self.target_combo.findData(scenario.action_device_id)
            if idx >= 0:
                self.target_combo.setCurrentIndex(idx)
            self.dur_spin.setValue(scenario.duration_seconds)
        else:
            self.thresh_edit.setText("35.0")
            self.dur_spin.setValue(DEFAULT_WATER_DURATION_SEC)

        form.addRow("Название:",   self.name_edit)
        form.addRow("Зона:",       self.zone_combo)
        form.addRow("Параметр:",   self.cond_combo)
        form.addRow("Условие:",    self.op_combo)
        form.addRow("Порог:",      self.thresh_edit)
        form.addRow("Действие:",   self.act_combo)
        form.addRow("Устройство:", self.target_combo)
        form.addRow("Длительность:", self.dur_spin)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def get_data(self):
        try:
            thresh = float(self.thresh_edit.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Порог должен быть числом")
            return None
        return {
            "name":             self.name_edit.text().strip() or "Сценарий",
            "zone_id":          self.zone_combo.currentData(),
            "condition_type":   self.cond_combo.currentText(),
            "condition_params": json.dumps({
                "threshold": thresh,
                "op":        self.op_combo.currentText(),
            }),
            "action_type":      self.act_combo.currentText(),
            "action_device_id": self.target_combo.currentData() or "",
            "action_params":    json.dumps({"duration_sec": self.dur_spin.value()}),
            "enabled":          True,
        }


class ScenariosWindow(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Название", "Зона", "Условие", "Действие", "Длит.", "Вкл"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table, stretch=3)

        btns = QHBoxLayout()
        self.btn_add    = QPushButton("Добавить")
        self.btn_del    = QPushButton("Удалить")
        self.btn_toggle = QPushButton("Вкл/Выкл")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_toggle)
        btns.addStretch(1)
        root.addLayout(btns)

        self.log = QLabel("")
        self.log.setStyleSheet("background:#f5f5f5; padding:6px; font-family:Consolas;")
        self.log.setMinimumHeight(120)
        self.log.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.log)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_toggle.clicked.connect(self.on_toggle)
        self.reload()

    def reload(self):
        db = SessionLocal()
        try:
            scenarios = db.query(Scenario).all()
            zones = {z.id: z.name for z in db.query(Zone).all()}
            self.table.setRowCount(len(scenarios))
            for r, sc in enumerate(scenarios):
                self.table.setItem(r, 0, QTableWidgetItem(sc.name))
                self.table.setItem(r, 1, QTableWidgetItem(zones.get(sc.zone_id, "—")))
                self.table.setItem(r, 2, QTableWidgetItem(
                    f"{sc.condition_type} {sc.condition} {sc.threshold_value}"
                ))
                self.table.setItem(r, 3, QTableWidgetItem(
                    f"{sc.action_type} → {sc.action_device_id or '—'}"
                ))
                self.table.setItem(r, 4, QTableWidgetItem(f"{sc.duration_seconds}s"))
                self.table.setItem(r, 5, QTableWidgetItem("Да" if sc.enabled else "Нет"))
        finally:
            db.close()

    def on_add(self):
        dlg = ScenarioDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data:
                return
            db = SessionLocal()
            try:
                db.add(Scenario(**data))
                db.commit()
            finally:
                db.close()
            self.reload()

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            return
        db = SessionLocal()
        try:
            scenarios = db.query(Scenario).all()
            if 0 <= r < len(scenarios):
                db.delete(scenarios[r])
                db.commit()
        finally:
            db.close()
        self.reload()

    def on_toggle(self):
        r = self.table.currentRow()
        if r < 0:
            return
        db = SessionLocal()
        try:
            scenarios = db.query(Scenario).all()
            if 0 <= r < len(scenarios):
                sc = scenarios[r]
                sc.enabled = not sc.enabled
                db.commit()
        finally:
            db.close()
        self.reload()