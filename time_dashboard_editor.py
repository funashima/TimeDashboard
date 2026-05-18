#!/usr/bin/env python3
import re
import shutil
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import QTime, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


CONFIG_PATH = Path.home() / "time_dashboard.yaml"

WEEKDAY_KEYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

WEEKDAY_LABELS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def default_config() -> dict[str, Any]:
    return {
        "workday_start": "09:00",
        "ui": {
            "font_family": "Futura ND Book",
            "font_point_size": 11,
            "header_font_point_size": 18,
            "class_status_font_point_size": 16,
            "countdown_font_point_size": 40,
            "background_color": "#f7f2ff",
        },
        "classes": {
            "monday": [
                {"title": "Game Theory", "start": "09:00", "end": "10:30"},
                {"title": "Design Patterns", "start": "13:00", "end": "14:30"},
            ],
            "tuesday": [],
            "wednesday": [],
            "thursday": [],
            "friday": [],
            "saturday": [],
            "sunday": [],
        },
        "departure_patterns": {
            "normal": {"label": "Normal", "time": "17:15"},
            "early": {"label": "Early Leave", "time": "16:30"},
            "late": {"label": "Late Work", "time": "18:30"},
            "hard": {"label": "Long Day", "time": "20:00"},
        },
    }


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_config()

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return default_config()

    return raw


def parse_qtime(value: Any, *, fallback: str = "09:00") -> QTime:
    if isinstance(value, time):
        return QTime(value.hour, value.minute)

    s = str(value).strip() if value is not None else fallback

    try:
        dt = datetime.strptime(s, "%H:%M")
        return QTime(dt.hour, dt.minute)
    except ValueError:
        dt = datetime.strptime(fallback, "%H:%M")
        return QTime(dt.hour, dt.minute)


def qtime_to_string(qtime: QTime) -> str:
    return qtime.toString("HH:mm")


def make_time_edit(value: Any, *, fallback: str = "09:00") -> QTimeEdit:
    editor = QTimeEdit()
    editor.setDisplayFormat("HH:mm")
    editor.setTime(parse_qtime(value, fallback=fallback))
    editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return editor


def table_text(table: QTableWidget, row: int, col: int) -> str:
    item = table.item(row, col)
    if item is None:
        return ""
    return item.text().strip()


def table_time(table: QTableWidget, row: int, col: int) -> str:
    widget = table.cellWidget(row, col)
    if isinstance(widget, QTimeEdit):
        return qtime_to_string(widget.time())
    return "00:00"


def is_start_before_end(start: str, end: str) -> bool:
    start_qt = parse_qtime(start)
    end_qt = parse_qtime(end)
    return start_qt.msecsTo(end_qt) > 0


class TimeDashboardConfigEditor(QMainWindow):
    def __init__(self, config_path: Path):
        super().__init__()

        self.config_path = config_path
        self.config = load_yaml_config(config_path)

        self.classes_by_weekday: dict[str, list[dict[str, str]]] = {
            weekday: self._normalize_class_list(
                self.config.get("classes", {}).get(weekday, [])
            )
            for weekday in WEEKDAY_KEYS
        }

        self.current_weekday = "monday"

        self.setWindowTitle("Time Dashboard Config Editor")
        self.resize(820, 640)

        self.tabs = QTabWidget()

        self.general_tab = self.create_general_tab()
        self.classes_tab = self.create_classes_tab()
        self.departure_tab = self.create_departure_tab()

        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.classes_tab, "Classes")
        self.tabs.addTab(self.departure_tab, "Departure Patterns")

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if self.config_path.exists():
            self.status_label.setText(f"Config file: {self.config_path}")
        else:
            self.status_label.setText(
                f"Config file not found. Defaults loaded. Save to create: {self.config_path}"
            )

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)

        reload_button = QPushButton("Reload")
        reload_button.clicked.connect(self.reload_config)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        button_row = QHBoxLayout()
        button_row.addWidget(self.status_label)
        button_row.addStretch()
        button_row.addWidget(save_button)
        button_row.addWidget(reload_button)
        button_row.addWidget(close_button)

        root = QVBoxLayout()
        root.addWidget(self.tabs)
        root.addLayout(button_row)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self.load_general_values()
        self.load_departure_table()
        self.load_weekday_table(self.current_weekday)

    def _normalize_class_list(self, value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []

        result: list[dict[str, str]] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            title = item.get("title") or item.get("subject") or ""
            start = item.get("start", "09:00")
            end = item.get("end", "10:30")

            result.append(
                {
                    "title": str(title),
                    "start": qtime_to_string(parse_qtime(start, fallback="09:00")),
                    "end": qtime_to_string(parse_qtime(end, fallback="10:30")),
                }
            )

        return result

    # ------------------------------------------------------------------
    # General tab
    # ------------------------------------------------------------------

    def create_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        form = QFormLayout()

        self.workday_start_edit = make_time_edit("09:00")

        self.font_family_edit = QLineEdit()
        self.font_combo = QFontComboBox()

        copy_font_button = QPushButton("Use Selected Font")
        copy_font_button.clicked.connect(self.copy_selected_font_name)

        font_row = QHBoxLayout()
        font_row.addWidget(self.font_family_edit)
        font_row.addWidget(self.font_combo)
        font_row.addWidget(copy_font_button)

        self.font_point_size_spin = QSpinBox()
        self.font_point_size_spin.setRange(6, 96)

        self.header_font_size_spin = QSpinBox()
        self.header_font_size_spin.setRange(6, 96)

        self.class_status_font_size_spin = QSpinBox()
        self.class_status_font_size_spin.setRange(6, 96)

        self.countdown_font_size_spin = QSpinBox()
        self.countdown_font_size_spin.setRange(8, 160)

        self.background_color_edit = QLineEdit()
        self.background_color_edit.setPlaceholderText("#f7f2ff")

        choose_color_button = QPushButton("Choose Color")
        choose_color_button.clicked.connect(self.choose_background_color)

        color_row = QHBoxLayout()
        color_row.addWidget(self.background_color_edit)
        color_row.addWidget(choose_color_button)

        form.addRow("Workday Start:", self.workday_start_edit)
        form.addRow("Font Family:", font_row)
        form.addRow("Base Font Size:", self.font_point_size_spin)
        form.addRow("Header Font Size:", self.header_font_size_spin)
        form.addRow("Class Status Font Size:", self.class_status_font_size_spin)
        form.addRow("Countdown Font Size:", self.countdown_font_size_spin)
        form.addRow("Background Color:", color_row)

        note = QLabel(
            "Font family should match a font name recognized by Qt/fontconfig. "
            "On Linux, you can check names with fc-list or fc-match.\n\n"
            "Background color should be a hex RGB value such as #f7f2ff. "
            "Use a very light color for better readability."
        )
        note.setWordWrap(True)

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def load_general_values(self) -> None:
        ui = self.config.get("ui", {})

        self.workday_start_edit.setTime(
            parse_qtime(self.config.get("workday_start", "09:00"), fallback="09:00")
        )

        font_family = str(ui.get("font_family", ""))
        self.font_family_edit.setText(font_family)

        if font_family:
            self.font_combo.setCurrentFont(QFont(font_family))

        self.font_point_size_spin.setValue(int(ui.get("font_point_size", 11)))
        self.header_font_size_spin.setValue(int(ui.get("header_font_point_size", 18)))
        self.class_status_font_size_spin.setValue(
            int(ui.get("class_status_font_point_size", 16))
        )
        self.countdown_font_size_spin.setValue(
            int(ui.get("countdown_font_point_size", 40))
        )
        self.background_color_edit.setText(
            str(ui.get("background_color", "#f7f2ff"))
        )

    def copy_selected_font_name(self) -> None:
        self.font_family_edit.setText(self.font_combo.currentFont().family())

    def choose_background_color(self) -> None:
        current = self.background_color_edit.text().strip()

        if not HEX_COLOR_PATTERN.match(current):
            current = "#f7f2ff"

        color = QColorDialog.getColor(
            QColor(current),
            self,
            "Select Background Color",
        )

        if color.isValid():
            self.background_color_edit.setText(color.name())

    # ------------------------------------------------------------------
    # Classes tab
    # ------------------------------------------------------------------

    def create_classes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        weekday_row = QHBoxLayout()
        weekday_row.addWidget(QLabel("Weekday:"))

        self.weekday_combo = QComboBox()
        for label in WEEKDAY_LABELS:
            self.weekday_combo.addItem(label)

        self.weekday_combo.currentIndexChanged.connect(self.on_weekday_changed)

        weekday_row.addWidget(self.weekday_combo)
        weekday_row.addStretch()

        self.class_table = QTableWidget()
        self.class_table.setColumnCount(3)
        self.class_table.setHorizontalHeaderLabels(["Start", "End", "Class Title"])
        self.class_table.horizontalHeader().setStretchLastSection(True)

        add_button = QPushButton("Add Class")
        add_button.clicked.connect(self.add_class_row)

        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_class_rows)

        class_button_row = QHBoxLayout()
        class_button_row.addWidget(add_button)
        class_button_row.addWidget(remove_button)
        class_button_row.addStretch()

        layout.addLayout(weekday_row)
        layout.addWidget(self.class_table)
        layout.addLayout(class_button_row)

        tab.setLayout(layout)
        return tab

    def on_weekday_changed(self, index: int) -> None:
        self.store_current_weekday_table()
        self.current_weekday = WEEKDAY_KEYS[index]
        self.load_weekday_table(self.current_weekday)

    def load_weekday_table(self, weekday: str) -> None:
        slots = self.classes_by_weekday.get(weekday, [])

        self.class_table.setRowCount(0)

        for slot in slots:
            self.add_class_row(
                title=slot.get("title", ""),
                start=slot.get("start", "09:00"),
                end=slot.get("end", "10:30"),
            )

    def store_current_weekday_table(self) -> None:
        self.classes_by_weekday[self.current_weekday] = self.read_class_table_rows(
            validate=False
        )

    def add_class_row(
        self,
        checked: bool = False,
        *,
        title: str = "New Class",
        start: str = "09:00",
        end: str = "10:30",
    ) -> None:
        row = self.class_table.rowCount()
        self.class_table.insertRow(row)

        self.class_table.setCellWidget(row, 0, make_time_edit(start, fallback="09:00"))
        self.class_table.setCellWidget(row, 1, make_time_edit(end, fallback="10:30"))
        self.class_table.setItem(row, 2, QTableWidgetItem(title))

    def remove_selected_class_rows(self) -> None:
        rows = sorted(
            {idx.row() for idx in self.class_table.selectedIndexes()},
            reverse=True,
        )

        for row in rows:
            self.class_table.removeRow(row)

    def read_class_table_rows(self, *, validate: bool) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []

        for row in range(self.class_table.rowCount()):
            start = table_time(self.class_table, row, 0)
            end = table_time(self.class_table, row, 1)
            title = table_text(self.class_table, row, 2)

            if not title and not validate:
                continue

            if validate:
                if not title:
                    raise ValueError(
                        f"Class title is empty in {self.current_weekday}, row {row + 1}."
                    )

                if not is_start_before_end(start, end):
                    raise ValueError(
                        f"Invalid class time in {self.current_weekday}, row {row + 1}: "
                        "start time must be earlier than end time."
                    )

            rows.append({"title": title, "start": start, "end": end})

        return rows

    # ------------------------------------------------------------------
    # Departure Patterns tab
    # ------------------------------------------------------------------

    def create_departure_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        self.departure_table = QTableWidget()
        self.departure_table.setColumnCount(3)
        self.departure_table.setHorizontalHeaderLabels(["Key", "Label", "Time"])
        self.departure_table.horizontalHeader().setStretchLastSection(True)

        add_button = QPushButton("Add Pattern")
        add_button.clicked.connect(self.add_departure_row)

        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_departure_rows)

        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()

        note = QLabel(
            "Key may contain letters, numbers, underscores, and hyphens only. "
            "Examples: normal, early, late, long_day."
        )
        note.setWordWrap(True)

        layout.addWidget(self.departure_table)
        layout.addLayout(button_row)
        layout.addWidget(note)

        tab.setLayout(layout)
        return tab

    def load_departure_table(self) -> None:
        patterns = self.config.get("departure_patterns", {})

        self.departure_table.setRowCount(0)

        if not isinstance(patterns, dict):
            return

        for key, item in patterns.items():
            if not isinstance(item, dict):
                continue

            self.add_departure_row(
                key=str(key),
                label=str(item.get("label", key)),
                time_value=str(item.get("time", "17:15")),
            )

    def add_departure_row(
        self,
        checked: bool = False,
        *,
        key: str | None = None,
        label: str = "New Pattern",
        time_value: str = "17:15",
    ) -> None:
        if key is None:
            key = self.next_available_departure_key()

        row = self.departure_table.rowCount()
        self.departure_table.insertRow(row)

        self.departure_table.setItem(row, 0, QTableWidgetItem(key))
        self.departure_table.setItem(row, 1, QTableWidgetItem(label))
        self.departure_table.setCellWidget(
            row, 2, make_time_edit(time_value, fallback="17:15")
        )

    def next_available_departure_key(self) -> str:
        existing = {
            table_text(self.departure_table, row, 0)
            for row in range(self.departure_table.rowCount())
        }

        base = "new_pattern"

        if base not in existing:
            return base

        i = 2
        while f"{base}_{i}" in existing:
            i += 1

        return f"{base}_{i}"

    def remove_selected_departure_rows(self) -> None:
        rows = sorted(
            {idx.row() for idx in self.departure_table.selectedIndexes()},
            reverse=True,
        )

        for row in rows:
            self.departure_table.removeRow(row)

    def read_departure_patterns(self) -> dict[str, dict[str, str]]:
        patterns: dict[str, dict[str, str]] = {}

        for row in range(self.departure_table.rowCount()):
            key = table_text(self.departure_table, row, 0)
            label = table_text(self.departure_table, row, 1)
            time_value = table_time(self.departure_table, row, 2)

            if not key:
                raise ValueError(f"Departure pattern key is empty in row {row + 1}.")

            if not KEY_PATTERN.match(key):
                raise ValueError(
                    f"Invalid departure pattern key in row {row + 1}: {key}\n"
                    "Use only letters, numbers, underscores, and hyphens."
                )

            if key in patterns:
                raise ValueError(f"Duplicate departure pattern key: {key}")

            if not label:
                raise ValueError(f"Departure pattern label is empty for key '{key}'.")

            patterns[key] = {"label": label, "time": time_value}

        if not patterns:
            raise ValueError("At least one departure pattern is required.")

        return patterns

    # ------------------------------------------------------------------
    # Save / Reload
    # ------------------------------------------------------------------

    def build_config(self) -> dict[str, Any]:
        self.store_current_weekday_table()

        background_color = self.background_color_edit.text().strip()

        if not HEX_COLOR_PATTERN.match(background_color):
            raise ValueError(
                "Invalid background color. Use a hex RGB value such as #f7f2ff."
            )

        classes: dict[str, list[dict[str, str]]] = {}

        for weekday in WEEKDAY_KEYS:
            if weekday == self.current_weekday:
                classes[weekday] = self.read_class_table_rows(validate=True)
            else:
                classes[weekday] = self.validate_stored_classes(weekday)

        return {
            "workday_start": qtime_to_string(self.workday_start_edit.time()),
            "ui": {
                "font_family": self.font_family_edit.text().strip(),
                "font_point_size": self.font_point_size_spin.value(),
                "header_font_point_size": self.header_font_size_spin.value(),
                "class_status_font_point_size": self.class_status_font_size_spin.value(),
                "countdown_font_point_size": self.countdown_font_size_spin.value(),
                "background_color": background_color,
            },
            "classes": classes,
            "departure_patterns": self.read_departure_patterns(),
        }

    def validate_stored_classes(self, weekday: str) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []

        for i, slot in enumerate(self.classes_by_weekday.get(weekday, []), start=1):
            title = slot.get("title", "").strip()
            start = slot.get("start", "09:00")
            end = slot.get("end", "10:30")

            if not title:
                raise ValueError(f"Class title is empty in {weekday}, row {i}.")

            if not is_start_before_end(start, end):
                raise ValueError(
                    f"Invalid class time in {weekday}, row {i}: "
                    "start time must be earlier than end time."
                )

            result.append({"title": title, "start": start, "end": end})

        return result

    def save_config(self) -> None:
        try:
            config = self.build_config()

            dumped = yaml.safe_dump(
                config,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )

            # Validate that the generated YAML can be read again.
            yaml.safe_load(dumped)

            backup_path: Path | None = None

            if self.config_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup_path = self.config_path.with_name(
                    f"{self.config_path.name}.{timestamp}.bak"
                )
                shutil.copy2(self.config_path, backup_path)

            with self.config_path.open("w", encoding="utf-8") as f:
                f.write(dumped)

            self.config = config
            self.status_label.setText(f"Saved: {self.config_path}")

            if backup_path is not None:
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Configuration saved.\n\nBackup created:\n{backup_path}",
                )
            else:
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Configuration saved:\n{self.config_path}",
                )

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def reload_config(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reload Configuration",
            "Discard unsaved changes and reload the configuration file?",
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.config = load_yaml_config(self.config_path)
            self.classes_by_weekday = {
                weekday: self._normalize_class_list(
                    self.config.get("classes", {}).get(weekday, [])
                )
                for weekday in WEEKDAY_KEYS
            }

            self.load_general_values()
            self.load_departure_table()

            self.current_weekday = WEEKDAY_KEYS[self.weekday_combo.currentIndex()]
            self.load_weekday_table(self.current_weekday)

            self.status_label.setText(f"Reloaded: {self.config_path}")

        except Exception as e:
            QMessageBox.critical(self, "Reload Failed", str(e))


def main() -> None:
    app = QApplication(sys.argv)
    window = TimeDashboardConfigEditor(CONFIG_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
