# Time Dashboard

Time Dashboard is a small PyQt6 desktop application for personal time awareness during a workday.

It displays today’s classes, the current or next class, the remaining time until the selected departure time, and the progress of the day from the configured workday start time.

The application is intentionally simple. It is not a calendar system, a task manager, or a productivity suite. It is a lightweight local dashboard for keeping a clear sense of the current day.

## Features

- Shows today’s class schedule
- Shows the current class, if one is in progress
- Shows the next class and the time remaining until it starts
- Allows selecting a departure pattern
- Displays a countdown until the selected departure time
- Displays progress from the workday start time to the selected departure time
- Uses a YAML configuration file
- Supports custom UI font settings

## Screenshot

Add a screenshot here if desired.

```text
Monday, May 18, 2026

Today’s Classes
09:00 - 10:30   Game Theory
13:00 - 14:30   Design Patterns

Current class: None
Next class: Design Patterns (13:00–14:30) / Starts in 01:12:40

Departure Pattern: Normal

Time Remaining Until Departure
03:42:15

Progress From Workday Start To Departure
54.8%
````

## Requirements

* Python 3.10 or later
* PyQt6
* PyYAML

Install dependencies:

```bash
pip install PyQt6 PyYAML
```

## Usage

Place `time_dashboard.py` and `time_dashboard.yaml` in the same directory.

Run:

```bash
python time_dashboard.py
```

The application reads its settings from:

```text
~/time_dashboard.yaml
```

## Configuration

Example `time_dashboard.yaml`:

```yaml
workday_start: "09:00"

ui:
  font_family: "Futura ND Book"
  font_point_size: 11
  header_font_point_size: 18
  class_status_font_point_size: 16
  countdown_font_point_size: 40

classes:
  monday:
    - title: "Game Theory"
      start: "09:00"
      end: "10:30"
    - title: "Design Patterns"
      start: "13:00"
      end: "14:30"

  tuesday:
    - title: "Rust Programming"
      start: "10:40"
      end: "12:10"

  wednesday:
    - title: "TDA / Topology"
      start: "09:00"
      end: "10:30"
    - title: "Software Security"
      start: "14:40"
      end: "16:10"

  thursday: []

  friday:
    - title: "Hardware Security"
      start: "13:00"
      end: "14:30"

  saturday: []

  sunday: []

departure_patterns:
  normal:
    label: "Normal"
    time: "17:15"

  early:
    label: "Early Leave"
    time: "16:30"

  late:
    label: "Late Work"
    time: "18:30"

  hard:
    label: "Long Day"
    time: "20:00"
```

## Font Settings

The UI font can be configured in the YAML file:

```yaml
ui:
  font_family: "Futura ND Book"
  font_point_size: 11
```

On Linux, available font family names can be checked with:

```bash
fc-list
```

For example:

```bash
fc-match "Futura ND Book"
```

If the requested font is not available, Qt may automatically select a fallback font. The application prints a warning when the selected font differs from the requested one.

## Design Philosophy

This application is designed as a personal instrument for time awareness.

It focuses on four questions:

1. What classes do I have today?
2. What is the current or next class?
3. How much time remains until departure?
4. How far has the workday progressed?

The goal is not to manage all tasks or events, but to provide a stable and minimal view of the current day.

## Notes

This repository is intended for personal use and small local customization.

If you publish your own configuration file, make sure it does not contain private or sensitive schedule information.

## License

MIT License

