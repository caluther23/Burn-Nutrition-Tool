"""
UI snapshot test: proves front-end changes don't alter any number the trainer sees.

Runs nutrition_report_app.py headlessly (streamlit.testing.v1.AppTest) for a set
of client profiles and records what is displayed: every metric (label, value,
delta, help), warnings, errors, captions, markdown text (HTML tags stripped),
the macro bar percentages, and the email draft.

    python test_ui_snapshot.py            # compare against ui_baseline.json
    python test_ui_snapshot.py --update   # rewrite the baseline (only after review!)

Metrics, warnings, errors, macro bar and email must match EXACTLY.
Captions and markdown must all still be present (new ones may be added); any
intentional removal/rewording goes in INTENTIONAL_CHANGES with a reason.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parent
APP = str(APP_DIR / "nutrition_report_app.py")
BASELINE = APP_DIR / "ui_baseline.json"

SEDENTARY = "Sedentary (little to no exercise)"
VERY = "Very Active (hard exercise 6-7 days/week)"

# Captions / markdown that were deliberately removed or reworded, with why.
INTENTIONAL_CHANGES: dict[str, str] = {}


def case(name, slider=50, meals=3, review=3, trainer="", **fields):
    return {"name": name, "slider": slider, "meals": meals, "review": review,
            "trainer": trainer, "fields": fields}


CASES = [
    # Every goal / intensity at the default body
    case("fatloss_low", in_fat_loss_type="Low"),
    case("fatloss_moderate"),
    case("fatloss_aggressive", in_fat_loss_type="Aggressive"),
    case("muscle_gain", in_primary_goal="Muscle Gain", in_goal_weight_lbs=195.0),
    case("recomp", in_primary_goal="Body Recomposition", in_goal_weight_lbs=175.0),
    case("maintenance", in_primary_goal="Maintenance", in_goal_weight_lbs=180.0),
    case("reverse_diet", in_primary_goal="Reverse Diet", in_goal_weight_lbs=190.0),
    # Slider sweep
    case("slider_0", slider=0),
    case("slider_25", slider=25),
    case("slider_75", slider=75),
    case("slider_100", slider=100),
    case("gain_slider_100", slider=100, in_primary_goal="Muscle Gain",
         in_goal_weight_lbs=195.0),
    # Meals / review date
    case("meals_4", meals=4),
    case("meals_5_no_review", meals=5, review=0),
    case("review_8", review=8),
    # Other bodies
    case("female_fatloss_low", slider=100, in_gender="Female", in_age=55, in_feet=5,
         in_inches=3, in_weight_lbs=145.0, in_goal_weight_lbs=130.0,
         in_activity_level=SEDENTARY, in_fat_loss_type="Low"),
    case("female_gain_very_active", in_gender="Female", in_age=24, in_feet=5,
         in_inches=6, in_weight_lbs=130.0, in_goal_weight_lbs=140.0,
         in_activity_level=VERY, in_primary_goal="Muscle Gain"),
    case("low_carb_warnings", slider=0, in_gender="Female", in_age=70, in_feet=4,
         in_inches=11, in_weight_lbs=110.0, in_goal_weight_lbs=100.0,
         in_activity_level=SEDENTARY, in_fat_loss_type="Aggressive"),
    case("negative_carbs", slider=0, in_gender="Female", in_age=90, in_feet=4,
         in_inches=11, in_weight_lbs=260.0, in_goal_weight_lbs=250.0,
         in_activity_level=SEDENTARY, in_primary_goal="Body Recomposition"),
    case("long_timeframe", in_weight_lbs=320.0, in_goal_weight_lbs=200.0),
    case("named_with_notes", meals=5, trainer="Coach Sam",
         in_client_name="Jordan Lee", in_client_notes="No dairy. Travels Mondays."),
    # Validation errors
    case("err_fatloss_goal_higher", in_goal_weight_lbs=190.0),
    case("err_gain_goal_lower", in_primary_goal="Muscle Gain"),
    case("err_gain_too_big", in_primary_goal="Muscle Gain", in_goal_weight_lbs=230.0),
    case("err_delta_150", in_weight_lbs=400.0, in_goal_weight_lbs=240.0),
]

# Dates that depend on the day the test runs.
_DATES = [
    (re.compile(r"\*\*[A-Z][a-z]+ \d{1,2}, \d{4}\*\*"), "**<DATE>**"),
    (re.compile(r"\*\*[A-Z][a-z]+ \d{4}\*\*"), "**<MONTH YEAR>**"),
]
_TAG = re.compile(r"<[^>]+>")


def _norm(text: str) -> str:
    for pattern, repl in _DATES:
        text = pattern.sub(repl, text)
    return text.strip()


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", html)).strip()


def run_case(c: dict) -> dict:
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in c["fields"].items():
        at.session_state[key] = value
    at.session_state["fat_carb_slider"] = c["slider"]
    at.session_state["meals_per_day"] = c["meals"]
    at.session_state["review_weeks"] = c["review"]
    at.session_state["trainer_name"] = c["trainer"]
    at.run()
    if at.exception:
        raise RuntimeError(f"{c['name']}: {[e.value for e in at.exception]}")

    macro_bar = []
    markdown = []
    for md in at.markdown:
        if "<style>" in md.value:
            continue
        if "macro-seg" in md.value:
            macro_bar = re.findall(r"(Protein|Fat|Carbs) (\d+)%", md.value)
            continue
        text = _norm(_text(md.value) if "<" in md.value else md.value)
        if text:
            markdown.append(text)

    return {
        "metrics": [[m.proto.label, m.proto.body, m.proto.delta, m.proto.help]
                    for m in at.metric],
        "warnings": [w.value for w in at.warning],
        "errors": [e.value for e in at.error],
        "macro_bar": [list(x) for x in macro_bar],
        "email": [c.value for c in at.code],
        "captions": [_norm(c.value) for c in at.caption],
        "markdown": markdown,
    }


def compare(name: str, base: dict, now: dict) -> list[str]:
    problems = []
    for key in ("metrics", "warnings", "errors", "macro_bar", "email"):
        if base[key] != now[key]:
            problems.append(f"{name}: {key} changed\n    was: {base[key]}\n    now: {now[key]}")
    for key, label in (("captions", "caption"), ("markdown", "markdown")):
        missing = [t for t in base[key] if t not in now[key] and t not in INTENTIONAL_CHANGES]
        for t in missing:
            problems.append(f"{name}: {label} missing: {t!r}")
    return problems


# ---------- Behavior checks (interaction sequences), added per stage ----------

def new_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def check_intensity_survives_goal_change() -> str | None:
    at = new_app()
    at.selectbox(key="in_fat_loss_type").select("Aggressive").run()
    at.selectbox(key="in_primary_goal").select("Maintenance").run()
    if not at.selectbox(key="in_fat_loss_type").disabled:
        return "intensity should be disabled for Maintenance"
    at.selectbox(key="in_primary_goal").select("Fat Loss").run()
    got = at.selectbox(key="in_fat_loss_type").value
    return None if got == "Aggressive" else f"intensity reset to {got!r}"


BEHAVIOR_CHECKS: list = [check_intensity_survives_goal_change]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    behavior_failures = []
    for check in BEHAVIOR_CHECKS:
        msg = check()
        if msg:
            behavior_failures.append(f"{check.__name__}: {msg}")
    print(f"Behavior checks:  {len(BEHAVIOR_CHECKS) - len(behavior_failures)}"
          f"/{len(BEHAVIOR_CHECKS)} passed")
    for f in behavior_failures:
        print("  - " + f)

    results = {c["name"]: run_case(c) for c in CASES}
    if "--update" in sys.argv or not BASELINE.exists():
        BASELINE.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"Baseline written: {len(results)} cases -> {BASELINE.name}")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = []
    for name, base in baseline.items():
        if name not in results:
            problems.append(f"{name}: case missing")
            continue
        problems += compare(name, base, results[name])

    print(f"UI cases checked: {len(results)}")
    if problems:
        print(f"UI mismatches:    {len(problems)}")
        for p in problems:
            print("  - " + p)
        return 1
    print("UI mismatches:    0")
    return 1 if behavior_failures else 0


if __name__ == "__main__":
    sys.exit(main())
