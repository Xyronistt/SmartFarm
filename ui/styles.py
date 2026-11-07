LIGHT_STYLE = """
QMainWindow, QWidget {
    background-color: #f6f8fb;
    color: #0f172a;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}

QWidget#Header { background-color: #ffffff; border-bottom: 1px solid #e5eaf1; }
QLabel#Logo { color: #0f172a; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }

QLabel#MqttStatus { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; }
QLabel#MqttStatus[connected="true"]  { background-color: #ecfdf5; color: #059669; }
QLabel#MqttStatus[connected="false"] { background-color: #fef2f2; color: #ef4444; }

QPushButton#ThemeToggle {
    background-color: #f8fafc;
    border: 1px solid #e5eaf1;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 15px;
    min-width: 36px;
    min-height: 32px;
}
QPushButton#ThemeToggle:hover { background-color: #ffffff; border-color: #cbd5e1; }

QTabWidget::pane { border: none; background-color: #f6f8fb; }
QTabBar { background-color: #ffffff; qproperty-drawBase: 0; }
QTabBar::tab {
    background-color: transparent; color: #64748b;
    padding: 12px 20px; font-size: 13px; font-weight: 500;
    border: none; border-bottom: 2px solid transparent; margin-right: 2px;
}
QTabBar::tab:hover { color: #0f172a; background-color: #f8fafc; }
QTabBar::tab:selected {
    color: #059669; border-bottom: 2px solid #10b981;
    background-color: #ecfdf5;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}

QWidget#ContentArea { background-color: #f6f8fb; }

QFrame#Card { background-color: #ffffff; border: 1px solid #e5eaf1; border-radius: 12px; }
QFrame#Card:hover { border-color: #cbd5e1; }
QLabel#CardTitle { font-size: 16px; font-weight: 700; color: #0f172a; letter-spacing: -0.01em; }
QLabel#CardSub   { color: #64748b; font-size: 12px; }

QTableWidget {
    background-color: transparent; border: none;
    gridline-color: transparent;
    alternate-background-color: #f8fafc;
    selection-background-color: #ecfdf5; selection-color: #0f172a; outline: none;
}
QTableWidget::item { padding: 10px 8px; border-bottom: 1px solid #f1f5f9; color: #0f172a; }
QTableWidget::item:hover { background-color: #f8fafc; }
QHeaderView::section {
    background-color: #f8fafc; color: #64748b;
    font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 10px 8px; border: none; border-bottom: 1px solid #e5eaf1;
}
QHeaderView::section:first { border-top-left-radius: 8px; }
QHeaderView::section:last  { border-top-right-radius: 8px; }

QPushButton {
    background-color: #ffffff; color: #0f172a;
    border: 1px solid #e5eaf1; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 500; min-height: 20px;
}
QPushButton:hover    { background-color: #f8fafc; border-color: #cbd5e1; }
QPushButton:pressed  { background-color: #f1f5f9; }
QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #e5eaf1; }

QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #059669);
    color: #ffffff; border: none; font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #34d399, stop:1 #10b981);
}
QPushButton#PrimaryButton:pressed { background-color: #047857; }

QPushButton[class="danger"] {
    background-color: #fef2f2; color: #ef4444; border: 1px solid #fecaca;
}
QPushButton[class="danger"]:hover { background-color: #fee2e2; }

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #ffffff; border: 1px solid #e5eaf1;
    border-radius: 8px; padding: 7px 11px; font-size: 13px; color: #0f172a;
    selection-background-color: #ecfdf5; selection-color: #059669; min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus,
QTextEdit:focus, QPlainTextEdit:focus { border-color: #10b981; background-color: #ffffff; }
QLineEdit:disabled, QComboBox:disabled { background-color: #f8fafc; color: #94a3b8; }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid #64748b;
    width: 0; height: 0; margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff; border: 1px solid #e5eaf1;
    border-radius: 8px; padding: 4px;
    selection-background-color: #ecfdf5; selection-color: #059669; outline: none;
}

QCheckBox { spacing: 8px; font-size: 13px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #cbd5e1; border-radius: 4px; background-color: #ffffff;
}
QCheckBox::indicator:hover { border-color: #10b981; }
QCheckBox::indicator:checked {
    background-color: #10b981; border-color: #10b981;
    image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3 8l3 3 7-7' stroke='white' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>);
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #94a3b8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; border: none; }

QDialog { background-color: #ffffff; }
QDialog QLabel { font-size: 13px; color: #0f172a; }
QDialogButtonBox QPushButton { min-width: 90px; }

QFrame#ChartCard { background-color: #ffffff; border: 1px solid #e5eaf1; border-radius: 10px; }

QMenu { background-color: #ffffff; border: 1px solid #e5eaf1; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 8px 16px; border-radius: 6px; font-size: 13px; color: #0f172a; }
QMenu::item:selected { background-color: #ecfdf5; color: #059669; }

QToolTip {
    background-color: #0f172a; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 10px; font-size: 12px;
}
"""


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #0b1220;
    color: #e6ecf5;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}

QWidget#Header { background-color: #111a2b; border-bottom: 1px solid #1f2a3f; }
QLabel#Logo { color: #e6ecf5; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; }

QLabel#MqttStatus { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; }
QLabel#MqttStatus[connected="true"]  { background-color: rgba(34,197,94,.15); color: #22c55e; }
QLabel#MqttStatus[connected="false"] { background-color: rgba(248,113,113,.15); color: #f87171; }

QPushButton#ThemeToggle {
    background-color: #16223a;
    border: 1px solid #1f2a3f;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 15px;
    min-width: 36px;
    min-height: 32px;
}
QPushButton#ThemeToggle:hover { background-color: #111a2b; border-color: #2c3b57; }

QTabWidget::pane { border: none; background-color: #0b1220; }
QTabBar { background-color: #111a2b; qproperty-drawBase: 0; }
QTabBar::tab {
    background-color: transparent; color: #8ea0ba;
    padding: 12px 20px; font-size: 13px; font-weight: 500;
    border: none; border-bottom: 2px solid transparent; margin-right: 2px;
}
QTabBar::tab:hover { color: #e6ecf5; background-color: #16223a; }
QTabBar::tab:selected {
    color: #22c55e; border-bottom: 2px solid #22c55e;
    background-color: rgba(34,197,94,.12);
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}

QWidget#ContentArea { background-color: #0b1220; }

QFrame#Card { background-color: #111a2b; border: 1px solid #1f2a3f; border-radius: 12px; }
QFrame#Card:hover { border-color: #2c3b57; }
QLabel#CardTitle { font-size: 16px; font-weight: 700; color: #e6ecf5; letter-spacing: -0.01em; }
QLabel#CardSub   { color: #8ea0ba; font-size: 12px; }

QTableWidget {
    background-color: transparent; border: none;
    gridline-color: transparent;
    alternate-background-color: #16223a;
    selection-background-color: rgba(34,197,94,.15); selection-color: #e6ecf5; outline: none;
}
QTableWidget::item { padding: 10px 8px; border-bottom: 1px solid #1a2439; color: #e6ecf5; }
QTableWidget::item:hover { background-color: #16223a; }
QHeaderView::section {
    background-color: #16223a; color: #8ea0ba;
    font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 10px 8px; border: none; border-bottom: 1px solid #1f2a3f;
}
QHeaderView::section:first { border-top-left-radius: 8px; }
QHeaderView::section:last  { border-top-right-radius: 8px; }

QPushButton {
    background-color: #16223a; color: #e6ecf5;
    border: 1px solid #1f2a3f; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 500; min-height: 20px;
}
QPushButton:hover    { background-color: #111a2b; border-color: #2c3b57; }
QPushButton:pressed  { background-color: #0f1729; }
QPushButton:disabled { background-color: #0f1729; color: #4a5b78; border-color: #1a2439; }

QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #22c55e, stop:1 #16a34a);
    color: #ffffff; border: none; font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #34d399, stop:1 #22c55e);
}
QPushButton#PrimaryButton:pressed { background-color: #15803d; }

QPushButton[class="danger"] {
    background-color: rgba(248,113,113,.12); color: #f87171;
    border: 1px solid rgba(248,113,113,.3);
}
QPushButton[class="danger"]:hover { background-color: rgba(248,113,113,.2); }

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #0f1729; border: 1px solid #1f2a3f;
    border-radius: 8px; padding: 7px 11px; font-size: 13px; color: #e6ecf5;
    selection-background-color: rgba(34,197,94,.25); selection-color: #22c55e; min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus,
QTextEdit:focus, QPlainTextEdit:focus { border-color: #22c55e; background-color: #111a2b; }
QLineEdit:disabled, QComboBox:disabled { background-color: #0f1729; color: #4a5b78; }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid #8ea0ba;
    width: 0; height: 0; margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #111a2b; border: 1px solid #1f2a3f;
    border-radius: 8px; padding: 4px;
    selection-background-color: rgba(34,197,94,.2); selection-color: #22c55e; outline: none;
    color: #e6ecf5;
}

QCheckBox { spacing: 8px; font-size: 13px; color: #e6ecf5; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #2c3b57; border-radius: 4px; background-color: #0f1729;
}
QCheckBox::indicator:hover { border-color: #22c55e; }
QCheckBox::indicator:checked {
    background-color: #22c55e; border-color: #22c55e;
    image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3 8l3 3 7-7' stroke='white' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>);
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #2c3b57; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3d4f70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #2c3b57; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #3d4f70; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; border: none; }

QDialog { background-color: #111a2b; }
QDialog QLabel { font-size: 13px; color: #e6ecf5; }
QDialogButtonBox QPushButton { min-width: 90px; }

QFrame#ChartCard { background-color: #111a2b; border: 1px solid #1f2a3f; border-radius: 10px; }

QMenu { background-color: #111a2b; border: 1px solid #1f2a3f; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 8px 16px; border-radius: 6px; font-size: 13px; color: #e6ecf5; }
QMenu::item:selected { background-color: rgba(34,197,94,.15); color: #22c55e; }

QToolTip {
    background-color: #e6ecf5; color: #0f172a; border: none;
    border-radius: 6px; padding: 6px 10px; font-size: 12px;
}
"""


def build_style(theme: str = "light") -> str:
    return DARK_STYLE if theme == "dark" else LIGHT_STYLE

MAIN_STYLE = LIGHT_STYLE