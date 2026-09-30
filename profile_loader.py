"""
profile_loader.py
-----------------
Front-end helper: turns an uploaded client-profile JSON into values that are
safe to put into the app's input widgets. No formulas live here.

A saved profile is written by the app itself, but files get hand-edited or come
from older versions. A value a widget can't display (a goal that isn't in the
list, an age outside 16-90, text where a number belongs) would crash the app on
the next run, so every field is checked against the widget that will show it.
"""

from __future__ import annotations

from nutrition_core import (
    ACTIVITY_MULTIPLIERS, FAT_LOSS_INTENSITIES, GENDERS, GOALS, ClientProfile,
)

# Widget bounds, shared with nutrition_report_app.py so the two can't drift.
AGE_RANGE = (16, 90)
FEET_RANGE = (4, 7)
INCHES_RANGE = (0, 11)
WEIGHT_RANGE = (80.0, 500.0)
MEALS_OPTIONS = [3, 4, 5]
REVIEW_WEEK_OPTIONS = [0, 1, 2, 3, 4, 6, 8]

_NUMERIC_FIELDS = {
    "age": (int, AGE_RANGE, "Age"),
    "feet": (int, FEET_RANGE, "Height (feet)"),
    "inches": (int, INCHES_RANGE, "Height (inches)"),
    "weight_lbs": (float, WEIGHT_RANGE, "Current weight"),
    "goal_weight_lbs": (float, WEIGHT_RANGE, "Goal weight"),
}
_CHOICE_FIELDS = {
    "gender": (GENDERS, "Gender"),
    "activity_level": (list(ACTIVITY_MULTIPLIERS), "Activity level"),
    "primary_goal": (GOALS, "Primary goal"),
    "fat_loss_type": (FAT_LOSS_INTENSITIES, "Fat loss intensity"),
    "meals_per_day": (MEALS_OPTIONS, "Meals per day"),
    "review_weeks": (REVIEW_WEEK_OPTIONS, "Check-in weeks"),
}
_TEXT_FIELDS = {"client_name", "client_notes"}


def sanitize_profile(data: object) -> tuple[dict, list[str]]:
    """
    Returns (values keyed by ClientProfile field, notes about anything adjusted).
    plan_date is not returned: the app always dates a plan when it's rendered.
    Raises ValueError if the file isn't a profile at all.
    """
    if not isinstance(data, dict):
        raise ValueError("expected a saved client profile (a JSON object)")
    known = set(ClientProfile.__dataclass_fields__)
    if not known & set(data):
        raise ValueError("no client profile fields found")

    defaults = ClientProfile().to_dict()
    values: dict = {}
    notes: list[str] = []

    for field, (kind, (lo, hi), label) in _NUMERIC_FIELDS.items():
        raw = data.get(field)
        if raw is None or isinstance(raw, bool):
            values[field] = defaults[field]
            notes.append(f"{label} was missing; using {defaults[field]:g}.")
            continue
        try:
            num = kind(float(raw)) if kind is int else float(raw)
        except (TypeError, ValueError):
            values[field] = defaults[field]
            notes.append(f"{label} ({raw!r}) wasn't a number; using {defaults[field]:g}.")
            continue
        clamped = min(max(num, kind(lo)), kind(hi))
        if clamped != num:
            notes.append(f"{label} {num:g} is outside {lo:g}-{hi:g}; set to {clamped:g}.")
        values[field] = clamped

    for field, (options, label) in _CHOICE_FIELDS.items():
        raw = data.get(field)
        if not isinstance(raw, bool) and raw in options:
            values[field] = options[options.index(raw)]   # 4.0 -> 4, same type as widget
            continue
        values[field] = defaults[field]
        # Non-Fat-Loss profiles legitimately save no intensity.
        if field == "fat_loss_type" and raw is None:
            continue
        # Profiles saved before these hand-off fields existed simply lack them.
        if field in ("meals_per_day", "review_weeks") and field not in data:
            continue
        what = "was missing" if raw is None else f"{raw!r} isn't an option"
        notes.append(f"{label} {what}; using {defaults[field]}.")

    for field in _TEXT_FIELDS:
        raw = data.get(field, "")
        values[field] = raw if isinstance(raw, str) else str(raw)

    return values, notes
