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
INTENTIONAL_CHANGES: dict[str, str] = {
    "**🥑 Fat**": "Stage 5: slider end labels moved into one HTML row for mobile",
    "**🍚 Carbs**": "Stage 5: slider end labels moved into one HTML row for mobile",
}


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


def check_reset_keeps_trainer() -> str | None:
    at = new_app()
    at.text_input(key="trainer_name").input("Coach Sam").run()
    at.text_input(key="trainer_email").input("sam@example.com").run()
    at.text_input(key="in_client_name").input("Jordan Lee").run()
    at.number_input(key="in_weight_lbs").set_value(210.0).run()
    at.radio(key="meals_per_day").set_value(5).run()
    at.button(key="confirm_reset").click().run()
    problems = []
    if at.text_input(key="in_client_name").value != "":
        problems.append("client name not cleared")
    if at.number_input(key="in_weight_lbs").value != 180.0:
        problems.append("weight not reset")
    if at.radio(key="meals_per_day").value != 3:
        problems.append("meals not reset")
    if at.text_input(key="trainer_name").value != "Coach Sam":
        problems.append("trainer name was cleared")
    if at.text_input(key="trainer_email").value != "sam@example.com":
        problems.append("trainer email was cleared")
    if at.session_state["_uploader_nonce"] != 1:
        problems.append("uploader not replaced")
    return "; ".join(problems) or None


def check_profile_loader() -> str | None:
    from nutrition_core import ClientProfile
    from profile_loader import sanitize_profile

    good = ClientProfile(client_name="A B", age=41, gender="Female",
                         primary_goal="Muscle Gain", fat_loss_type=None,
                         goal_weight_lbs=190.0, meals_per_day=5, review_weeks=8,
                         plan_date="2026-07-01").to_dict()
    vals, notes = sanitize_profile(good)
    expect_good = {k: v for k, v in good.items() if k != "plan_date"}
    expect_good["fat_loss_type"] = "Moderate"
    if vals != expect_good or notes:
        return f"clean profile altered: {vals} {notes}"

    old_file = {k: v for k, v in good.items()
                if k not in ("meals_per_day", "review_weeks", "plan_date")}
    vals, notes = sanitize_profile(old_file)
    if notes or vals["meals_per_day"] != 3 or vals["review_weeks"] != 3:
        return f"older profile without hand-off fields mishandled: {notes}"

    bad = good | {"primary_goal": "Bulk", "weight_lbs": 900, "age": "old",
                  "gender": None, "feet": 6.0, "meals_per_day": 7, "review_weeks": 4.0}
    del bad["inches"]
    vals, notes = sanitize_profile(bad)
    expect = {"primary_goal": "Fat Loss", "weight_lbs": 500.0, "age": 30,
              "gender": "Male", "feet": 6, "inches": 8, "meals_per_day": 3,
              "review_weeks": 4}
    wrong = {k: vals[k] for k in expect if vals[k] != expect[k]}
    if wrong or len(notes) != 6:
        return f"bad profile not sanitized: {wrong} notes={notes}"
    if (type(vals["weight_lbs"]) is not float or type(vals["feet"]) is not int
            or type(vals["review_weeks"]) is not int):
        return "numeric types not coerced for widgets"

    for junk in ([1, 2], {"foo": 1}, "text"):
        try:
            sanitize_profile(junk)
            return f"accepted non-profile {junk!r}"
        except ValueError:
            pass
    return None


def check_stale_pdf_not_offered() -> str | None:
    stale_msg = "Inputs changed since the last PDF was built"

    def pdf_downloads(at):
        return [d for d in at.get("download_button") if "Download PDF" in d.proto.label]

    for change in ("weight", "trainer_email", "anchors"):
        at = new_app()
        next(b for b in at.button if "Build PDF" in b.label).click().run()
        if not pdf_downloads(at):
            return "no PDF download after building"
        if change == "weight":
            at.number_input(key="in_weight_lbs").set_value(190.0).run()
        elif change == "trainer_email":
            at.text_input(key="trainer_email").input("new@example.com").run()
        else:
            next(c for c in at.checkbox if c.label == "Food portion anchors").uncheck().run()
        if pdf_downloads(at):
            return f"stale PDF still offered after {change} change"
        if not any(stale_msg in c.value for c in at.caption):
            return f"no stale-PDF notice after {change} change"
    return None


BEHAVIOR_CHECKS: list = [check_intensity_survives_goal_change, check_reset_keeps_trainer,
                         check_profile_loader, check_stale_pdf_not_offered]


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
