"""
batch.py
--------
Multi-client batch mode: turn a CSV of clients into a ZIP of branded PDFs.

Kept separate from the Streamlit app so the parsing/validation logic is
testable on its own. No calorie or macro math lives here — it only maps CSV
rows onto ClientProfile and calls the existing pipeline.
"""

from __future__ import annotations

import csv
import io
import zipfile

from nutrition_core import (
    ACTIVITY_MULTIPLIERS, FAT_LOSS_INTENSITIES, GENDERS, GOALS,
    ClientProfile, build_plan, validate_profile,
)
from pdf_report import generate_pdf

# Canonical column names -> ClientProfile field. Header matching is
# case-insensitive and ignores spaces/underscores.
COLUMN_ALIASES = {
    "name": "client_name",
    "clientname": "client_name",
    "age": "age",
    "gender": "gender",
    "sex": "gender",
    "feet": "feet",
    "ft": "feet",
    "heightfeet": "feet",
    "inches": "inches",
    "in": "inches",
    "heightinches": "inches",
    "weight": "weight_lbs",
    "weightlbs": "weight_lbs",
    "currentweight": "weight_lbs",
    "goalweight": "goal_weight_lbs",
    "goalweightlbs": "goal_weight_lbs",
    "activity": "activity_level",
    "activitylevel": "activity_level",
    "goal": "primary_goal",
    "primarygoal": "primary_goal",
    "intensity": "fat_loss_type",
    "fatlosstype": "fat_loss_type",
    "fatlossintensity": "fat_loss_type",
    "notes": "client_notes",
    "trainernotes": "client_notes",
    "meals": "meals_per_day",
    "mealsperday": "meals_per_day",
    "review": "review_weeks",
    "reviewweeks": "review_weeks",
}

# Fuzzy matching for enum-style columns so "moderate", "Fat loss", "female"
# resolve without exact-string fussiness.
_ACTIVITY_KEYS = {a.split(" (")[0].lower(): a for a in ACTIVITY_MULTIPLIERS}


def _norm(header: str) -> str:
    return header.strip().lower().replace(" ", "").replace("_", "")


def _match_activity(value: str) -> str:
    v = value.strip().lower()
    for key, full in _ACTIVITY_KEYS.items():
        if v in key or key in v:
            return full
    # single-word shortcuts
    for full in ACTIVITY_MULTIPLIERS:
        if v and v.split()[0] in full.lower():
            return full
    return "Moderately Active (moderate exercise 3-5 days/week)"


def _match_choice(value: str, options: list[str], default: str) -> str:
    v = value.strip().lower()
    for o in options:
        if v == o.lower():
            return o
    for o in options:
        if v and (v in o.lower() or o.lower() in v):
            return o
    return default


def parse_row(raw: dict) -> ClientProfile:
    """Map one CSV row (already header-normalized) onto a ClientProfile."""
    data: dict = {}
    for key, value in raw.items():
        field = COLUMN_ALIASES.get(_norm(key))
        if not field or value is None or str(value).strip() == "":
            continue
        value = str(value).strip()

        if field in ("age", "feet", "inches", "meals_per_day", "review_weeks"):
            try:
                data[field] = int(float(value))
            except ValueError:
                pass
        elif field in ("weight_lbs", "goal_weight_lbs"):
            try:
                data[field] = float(value)
            except ValueError:
                pass
        elif field == "gender":
            data[field] = _match_choice(value, GENDERS, "Male")
        elif field == "primary_goal":
            data[field] = _match_choice(value, GOALS, "Fat Loss")
        elif field == "fat_loss_type":
            data[field] = _match_choice(value, FAT_LOSS_INTENSITIES, "Moderate")
        elif field == "activity_level":
            data[field] = _match_activity(value)
        else:
            data[field] = value

    # Fat loss type only applies to Fat Loss goal
    if data.get("primary_goal") != "Fat Loss":
        data["fat_loss_type"] = None
    else:
        data.setdefault("fat_loss_type", "Moderate")

    return ClientProfile.from_dict(data)


def process_csv(file_bytes: bytes, *, trainer_name: str = "",
                trainer_email: str = "", gym_location: str = "",
                include_member_guide: bool = True, show_food_anchors: bool = True,
                show_sample_day: bool = True, show_tracker: bool = True,
                fat_carb_balance: int = 50) -> tuple[bytes, list[dict]]:
    """Return (zip_bytes, results) where results logs per-row status."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    results: list[dict] = []
    zip_buffer = io.BytesIO()
    used_names: dict[str, int] = {}

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, raw in enumerate(reader, start=1):
            try:
                profile = parse_row(raw)
                errors = validate_profile(profile)
                if errors:
                    results.append({"row": i, "name": profile.client_name or "(unnamed)",
                                    "status": "skipped", "detail": "; ".join(errors)})
                    continue

                plan = build_plan(profile, fat_carb_balance)
                pdf = generate_pdf(
                    profile, plan, trainer_name=trainer_name,
                    include_member_guide=include_member_guide,
                    trainer_email=trainer_email, gym_location=gym_location,
                    show_food_anchors=show_food_anchors,
                    show_sample_day=show_sample_day, show_tracker=show_tracker,
                )
                safe = ("".join(c for c in profile.client_name
                                if c.isalnum() or c in " -_").strip().replace(" ", "_")
                        or f"Client_{i}")
                # de-duplicate identical names
                if safe in used_names:
                    used_names[safe] += 1
                    safe = f"{safe}_{used_names[safe]}"
                else:
                    used_names[safe] = 1

                zf.writestr(f"{safe}.pdf", pdf.getvalue())
                results.append({"row": i, "name": profile.client_name or f"Client {i}",
                                "status": "ok", "detail": f"{plan.target_calories} cal"})
            except Exception as exc:  # noqa: BLE001 - report, don't crash the batch
                results.append({"row": i, "name": raw.get("name", f"row {i}"),
                                "status": "error", "detail": str(exc)[:120]})

    zip_buffer.seek(0)
    return zip_buffer.getvalue(), results


def sample_csv_template() -> str:
    """A ready-to-fill CSV header row plus one example line."""
    header = ("name,age,gender,feet,inches,weight,goal_weight,activity,goal,"
              "intensity,meals,review,notes")
    example = ("Jane Doe,34,Female,5,5,168,145,Moderately Active,Fat Loss,"
               "Moderate,4,3,Dairy sensitivity")
    return header + "\n" + example + "\n"
