#!/usr/bin/env python3
import sys
import yaml
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from pathlib import Path
import os

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QFontInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


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

MONTH_LABELS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


@dataclass(frozen=True)
class ClassSlot:
    title: str
    start: time
    end: time


@dataclass(frozen=True)
class DeparturePattern:
    key: str
    label: str
    time: time


@dataclass(frozen=True)
class UIConfig:
    font_family: str
    font_point_size: int
    header_font_point_size: int
    class_status_font_point_size: int
    countdown_font_point_size: int


@dataclass(frozen=True)
class AppConfig:
    workday_start: time
    classes: dict[str, list[ClassSlot]]
    departure_patterns: dict[str, DeparturePattern]
    ui: UIConfig


def parse_time(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


def at_date(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def format_timedelta(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds()))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Config file is empty: {path}")

    workday_start = parse_time(raw.get("workday_start", "09:00"))

    ui_raw = raw.get("ui", {})

    ui = UIConfig(
        font_family=str(ui_raw.get("font_family", "")),
        font_point_size=int(ui_raw.get("font_point_size", 11)),
        header_font_point_size=int(ui_raw.get("header_font_point_size", 18)),
        class_status_font_point_size=int(
            ui_raw.get("class_status_font_point_size", 16)
        ),
        countdown_font_point_size=int(ui_raw.get("countdown_font_point_size", 40)),
    )

    classes: dict[str, list[ClassSlot]] = {}

    for weekday in WEEKDAY_KEYS:
        slots: list[ClassSlot] = []

        for item in raw.get("classes", {}).get(weekday, []):
            # "subject" is accepted for backward compatibility.
            title = item.get("title") or item.get("subject")

            if not title:
                raise ValueError(f"Class title is missing in {weekday}: {item}")

            slots.append(
                ClassSlot(
                    title=str(title),
                    start=parse_time(item["start"]),
                    end=parse_time(item["end"]),
                )
            )

        slots.sort(key=lambda slot: slot.start)
        classes[weekday] = slots

    departure_patterns: dict[str, DeparturePattern] = {}

    for key, item in raw.get("departure_patterns", {}).items():
        departure_patterns[str(key)] = DeparturePattern(
            key=str(key),
            label=str(item.get("label", key)),
            time=parse_time(item["time"]),
        )

    if not departure_patterns:
        raise ValueError("No departure_patterns are defined in the YAML file.")

    return AppConfig(
        workday_start=workday_start,
        classes=classes,
        departure_patterns=departure_patterns,
        ui=ui,
    )


def apply_application_font(app: QApplication, ui: UIConfig) -> None:
    if not ui.font_family:
        return

    font = QFont(ui.font_family, ui.font_point_size)
    app.setFont(font)

    actual_family = QFontInfo(app.font()).family()

    if actual_family != ui.font_family:
        print(
            f"Warning: requested font '{ui.font_family}', "
            f"but Qt selected '{actual_family}'."
        )


class TimeDashboard(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.config = config
        self.current_date = date.today()
        self.today_slots: list[ClassSlot] = []

        self.setWindowTitle("Time Dashboard")
        self.resize(640, 520)

        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet(
            f"font-size: {self.config.ui.header_font_point_size}pt;"
        )

        self.class_table = QTableWidget()
        self.class_table.setColumnCount(3)
        self.class_table.setHorizontalHeaderLabels(["Start", "End", "Class"])
        self.class_table.horizontalHeader().setStretchLastSection(True)

        self.pattern_combo = QComboBox()
        for key, pattern in self.config.departure_patterns.items():
            self.pattern_combo.addItem(pattern.label, key)

        self.current_class_label = QLabel()
        self.current_class_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_class_label.setStyleSheet(
            f"font-size: {self.config.ui.class_status_font_point_size}pt;"
        )

        self.next_class_label = QLabel()
        self.next_class_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_class_label.setStyleSheet(
            f"font-size: {self.config.ui.class_status_font_point_size}pt;"
        )

        self.countdown_label = QLabel()
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(
            f"font-size: {self.config.ui.countdown_font_point_size}pt;"
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(True)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Departure Pattern:"))
        pattern_row.addWidget(self.pattern_combo)

        layout = QVBoxLayout()
        layout.addWidget(self.date_label)

        layout.addWidget(QLabel("Today’s Classes"))
        layout.addWidget(self.class_table)

        layout.addWidget(QLabel("Class Status"))
        layout.addWidget(self.current_class_label)
        layout.addWidget(self.next_class_label)

        layout.addLayout(pattern_row)

        layout.addWidget(QLabel("Time Remaining Until Departure"))
        layout.addWidget(self.countdown_label)

        layout.addWidget(QLabel("Progress From Workday Start To Departure"))
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.populate_today_classes()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time_display)
        self.timer.start(1000)

        self.pattern_combo.currentIndexChanged.connect(self.update_time_display)
        self.update_time_display()

    def current_departure_pattern(self) -> DeparturePattern:
        key = self.pattern_combo.currentData()
        return self.config.departure_patterns[key]

    def populate_today_classes(self) -> None:
        today = self.current_date
        weekday_index = today.weekday()
        weekday_key = WEEKDAY_KEYS[weekday_index]

        self.date_label.setText(
            f"{WEEKDAY_LABELS[weekday_index]}, "
            f"{MONTH_LABELS[today.month - 1]} {today.day}, {today.year}"
        )

        self.today_slots = self.config.classes.get(weekday_key, [])

        if not self.today_slots:
            self.class_table.setRowCount(1)
            self.class_table.setItem(0, 0, QTableWidgetItem("-"))
            self.class_table.setItem(0, 1, QTableWidgetItem("-"))
            self.class_table.setItem(0, 2, QTableWidgetItem("No classes today"))
            return

        self.class_table.setRowCount(len(self.today_slots))

        for row, slot in enumerate(self.today_slots):
            self.class_table.setItem(
                row, 0, QTableWidgetItem(slot.start.strftime("%H:%M"))
            )
            self.class_table.setItem(
                row, 1, QTableWidgetItem(slot.end.strftime("%H:%M"))
            )
            self.class_table.setItem(row, 2, QTableWidgetItem(slot.title))

    def update_time_display(self) -> None:
        now = datetime.now()

        # Refresh the table if the application remains open across midnight.
        if now.date() != self.current_date:
            self.current_date = now.date()
            self.populate_today_classes()

        self.update_departure_countdown(now)
        self.update_workday_progress(now)
        self.update_class_status(now)

    def update_departure_countdown(self, now: datetime) -> None:
        pattern = self.current_departure_pattern()
        departure_dt = at_date(now.date(), pattern.time)

        if now <= departure_dt:
            remaining = departure_dt - now
            self.countdown_label.setText(format_timedelta(remaining))
        else:
            overtime = now - departure_dt
            self.countdown_label.setText(f"+{format_timedelta(overtime)}")

    def update_workday_progress(self, now: datetime) -> None:
        pattern = self.current_departure_pattern()

        start_dt = at_date(now.date(), self.config.workday_start)
        departure_dt = at_date(now.date(), pattern.time)

        total_seconds = (departure_dt - start_dt).total_seconds()
        elapsed_seconds = (now - start_dt).total_seconds()

        if total_seconds <= 0:
            ratio = 1.0
        else:
            ratio = elapsed_seconds / total_seconds

        clamped_ratio = max(0.0, min(1.0, ratio))

        self.progress_bar.setValue(int(clamped_ratio * 1000))
        self.progress_bar.setFormat(f"{clamped_ratio * 100:.1f}%")

        if now < start_dt:
            self.status_label.setText("Before workday start.")
        elif now <= departure_dt:
            elapsed_min = int(max(0, elapsed_seconds) // 60)
            remaining_min = int(max(0, (departure_dt - now).total_seconds()) // 60)

            self.status_label.setText(
                f"{elapsed_min} minutes elapsed since "
                f"{self.config.workday_start.strftime('%H:%M')} / "
                f"{remaining_min} minutes remaining."
            )
        else:
            overtime_min = int((now - departure_dt).total_seconds() // 60)
            self.status_label.setText(
                f"{overtime_min} minutes past the selected departure time."
            )

    def update_class_status(self, now: datetime) -> None:
        current_slot: ClassSlot | None = None
        next_slot: ClassSlot | None = None

        for slot in self.today_slots:
            start_dt = at_date(now.date(), slot.start)
            end_dt = at_date(now.date(), slot.end)

            if start_dt <= now < end_dt:
                current_slot = slot
                break

            if now < start_dt and next_slot is None:
                next_slot = slot

        if current_slot is not None:
            end_dt = at_date(now.date(), current_slot.end)
            remaining = end_dt - now

            self.current_class_label.setText(
                f"Current class: {current_slot.title} "
                f"({current_slot.start.strftime('%H:%M')}–"
                f"{current_slot.end.strftime('%H:%M')}) "
                f"/ Ends in {format_timedelta(remaining)}"
            )

            next_slot = self.find_next_class_after(current_slot)

            if next_slot is not None:
                next_start_dt = at_date(now.date(), next_slot.start)
                until_next = next_start_dt - now

                self.next_class_label.setText(
                    f"Next class: {next_slot.title} "
                    f"({next_slot.start.strftime('%H:%M')}–"
                    f"{next_slot.end.strftime('%H:%M')}) "
                    f"/ Starts in {format_timedelta(until_next)}"
                )
            else:
                self.next_class_label.setText("Next class: None today")

            return

        self.current_class_label.setText("Current class: None")

        if next_slot is not None:
            start_dt = at_date(now.date(), next_slot.start)
            remaining = start_dt - now

            self.next_class_label.setText(
                f"Next class: {next_slot.title} "
                f"({next_slot.start.strftime('%H:%M')}–"
                f"{next_slot.end.strftime('%H:%M')}) "
                f"/ Starts in {format_timedelta(remaining)}"
            )
        else:
            if self.today_slots:
                self.next_class_label.setText("Next class: None today")
            else:
                self.next_class_label.setText("Next class: No classes today")

    def find_next_class_after(self, current_slot: ClassSlot) -> ClassSlot | None:
        found_current = False

        for slot in self.today_slots:
            if found_current:
                return slot

            if slot == current_slot:
                found_current = True

        return None


def main() -> None:
    config_file = "time_dashboard.yaml"
    config_path = Path(os.path.join(os.environ["HOME"], config_file))
    config = load_config(config_path)

    app = QApplication(sys.argv)
    apply_application_font(app, config.ui)

    window = TimeDashboard(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
