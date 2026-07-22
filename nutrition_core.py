"""
nutrition_core.py
-----------------
Pure calculation layer for the Burn Boot Camp Client Nutrition Report.

Contains NO Streamlit code so it can be unit-tested, reused, or swapped into
another front end. All formulas preserved exactly as authored.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

# ============================================================
#  CONSTANTS
# ============================================================

LBS_PER_KG = 2.20462
CM_PER_FOOT = 30.48
CM_PER_INCH = 2.54

CAL_PER_G_PROTEIN = 4
CAL_PER_G_CARB = 4
CAL_PER_G_FAT = 9

WEEKS_PER_MONTH = 4.345

# Threshold below which a low-carb warning is surfaced (item #4)
LOW_CARB_WARNING_THRESHOLD_G = 50

ACTIVITY_MULTIPLIERS = {
    "Sedentary (little to no exercise)": 1.2,
    "Lightly Active (light exercise 1-3 days/week)": 1.375,
    "Moderately Active (moderate exercise 3-5 days/week)": 1.55,
    "Very Active (hard exercise 6-7 days/week)": 1.725,
    "Super Active (very hard exercise + physical job)": 1.9,
}
DEFAULT_ACTIVITY_MULTIPLIER = 1.55

GOAL_ADJUSTMENTS = {
    "Fat Loss": -0.20,
    "Muscle Gain": 0.10,
    "Body Recomposition": -0.05,
    "Maintenance": 0.0,
    "Reverse Diet": 0.05,
}

FAT_LOSS_TDEE_FACTORS = {
    "Low": 0.90,
    "Moderate": 0.85,
    "Aggressive": 0.80,
}

# Protein multipliers by goal. Fat Loss anchors on GOAL weight; others on CURRENT weight.
PROTEIN_RULES = {
    "Fat Loss": ("goal", 1.1),
    "Muscle Gain": ("current", 0.9),
    "Reverse Diet": ("current", 0.9),
    "Body Recomposition": ("current", 1.0),
    "Maintenance": ("current", 1.0),
}
DEFAULT_PROTEIN_RULE = ("current", 1.0)

# Fat as a percentage of TOTAL calories.
# Baseline (slider centered) = 0.30, matching the documented baseline macro split.
# Slider 0 (all Fat) -> 0.40 ; slider 100 (all Carbs) -> 0.20 ; slider 50 -> 0.30
BASELINE_FAT_PCT = 0.30
FAT_PCT_SWING = 0.10  # +/- around baseline

# Weekly rate of change assumptions for goal timeframe estimates (lbs/week)
TIMEFRAME_RATES = {
    "Fat Loss": 0.75,
    "Muscle Gain": 0.40,
}

GOALS = ["Fat Loss", "Muscle Gain", "Body Recomposition", "Maintenance", "Reverse Diet"]
FAT_LOSS_INTENSITIES = ["Low", "Moderate", "Aggressive"]
GENDERS = ["Male", "Female"]

# Goals that require goal weight > current weight
GAIN_GOALS = {"Muscle Gain", "Reverse Diet"}
LOSS_GOALS = {"Fat Loss"}


# ============================================================
#  UNIT CONVERSION
# ============================================================

def lbs_to_kg(weight_lbs: float) -> float:
    return weight_lbs / LBS_PER_KG


def feet_inches_to_cm(feet: int, inches: int) -> float:
    return (feet * CM_PER_FOOT) + (inches * CM_PER_INCH)


# ============================================================
#  CORE FORMULAS  (unchanged from original)
# ============================================================

def calculate_bmr_mifflin(age: int, weight_lbs: float, height_feet: int,
                          height_inches: int, gender: str) -> float:
    """Mifflin-St Jeor basal metabolic rate."""
    weight_kg = lbs_to_kg(weight_lbs)
    height_cm = feet_inches_to_cm(height_feet, height_inches)

    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    bmr += 5 if gender == "Male" else -161
    return round(bmr, 1)


def get_tdee_multiplier(activity: str) -> float:
    return ACTIVITY_MULTIPLIERS.get(activity, DEFAULT_ACTIVITY_MULTIPLIER)


def get_goal_adjustment(goal: str) -> float:
    return GOAL_ADJUSTMENTS.get(goal, 0.0)


def calculate_target_calories(tdee: int, goal: str,
                              fat_loss_intensity: Optional[str] = None) -> tuple[int, float]:
    """
    Returns (target_calories, effective_adjustment_fraction).

    Fat Loss uses the intensity-specific TDEE factor. The returned adjustment is
    DERIVED from that factor so display text can never drift from the math.
    """
    if goal == "Fat Loss":
        factor = FAT_LOSS_TDEE_FACTORS.get(
            fat_loss_intensity, FAT_LOSS_TDEE_FACTORS["Moderate"]
        )
        return round(tdee * factor), factor - 1.0

    adjustment = get_goal_adjustment(goal)
    return round(tdee * (1 + adjustment)), adjustment


def calculate_protein(goal: str, current_weight_lbs: float,
                      goal_weight_lbs: float) -> int:
    """Protein target in grams, anchored per the goal's rule."""
    anchor, multiplier = PROTEIN_RULES.get(goal, DEFAULT_PROTEIN_RULE)
    weight = goal_weight_lbs if anchor == "goal" else current_weight_lbs
    return round(weight * multiplier)


def fat_pct_from_slider(balance: int) -> float:
    """
    Map the 0-100 Fat<->Carb slider onto a fat percentage of total calories.

    balance=0   -> 0.40 (higher fat)
    balance=50  -> 0.30 (baseline)
    balance=100 -> 0.20 (higher carb)
    """
    return BASELINE_FAT_PCT + FAT_PCT_SWING * (1 - balance / 50.0)


def split_fat_and_carbs(target_calories: int, protein_g: float,
                        fat_pct: float) -> tuple[float, float]:
    """
    Fat is a percentage of TOTAL calories (unchanged behavior).
    Carbs absorb the remainder after protein and fat.
    """
    protein_cal = protein_g * CAL_PER_G_PROTEIN
    remaining_cal = target_calories - protein_cal

    fat_g = round((target_calories * fat_pct) / CAL_PER_G_FAT, 1)
    fat_cal = fat_g * CAL_PER_G_FAT
    carb_g = round((remaining_cal - fat_cal) / CAL_PER_G_CARB, 1)

    return fat_g, carb_g


def estimate_timeframe(current_weight: float, goal_weight: float,
                       goal: str) -> Optional[tuple[int, int, float]]:
    """Returns (months, days, total_weeks) or None if goal has no weight target."""
    rate = TIMEFRAME_RATES.get(goal)
    if rate is None:
        return None

    weight_diff = abs(current_weight - goal_weight)
    if weight_diff == 0:
        return 0, 0, 0.0

    weeks = weight_diff / rate
    months = int(weeks // WEEKS_PER_MONTH)
    days = int((weeks % WEEKS_PER_MONTH) * 7)
    return months, days, round(weeks, 1)


# ============================================================
#  RESULT CONTAINERS
# ============================================================

@dataclass
class ClientProfile:
    """Everything the trainer entered."""
    client_name: str = ""
    age: int = 30
    gender: str = "Male"
    feet: int = 5
    inches: int = 8
    weight_lbs: float = 180.0
    goal_weight_lbs: float = 160.0
    activity_level: str = "Moderately Active (moderate exercise 3-5 days/week)"
    primary_goal: str = "Fat Loss"
    fat_loss_type: Optional[str] = "Moderate"
    client_notes: str = ""

    @property
    def height_display(self) -> str:
        return f"{self.feet}'{self.inches}\""

    @property
    def first_name(self) -> str:
        return self.client_name.split()[0] if self.client_name.strip() else "there"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClientProfile":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class NutritionPlan:
    """Everything derived from a ClientProfile."""
    bmr: float
    tdee: int
    target_calories: int
    adjustment: float
    protein_g: int
    fat_g: float
    carb_g: float
    fat_pct: float
    timeframe: Optional[tuple[int, int, float]] = None
    warnings: list[str] = field(default_factory=list)

    # ---- derived display values ----
    @property
    def protein_cal(self) -> float:
        return self.protein_g * CAL_PER_G_PROTEIN

    @property
    def fat_cal(self) -> float:
        return self.fat_g * CAL_PER_G_FAT

    @property
    def carb_cal(self) -> float:
        return self.carb_g * CAL_PER_G_CARB

    @property
    def macro_calorie_total(self) -> float:
        return self.protein_cal + self.fat_cal + self.carb_cal

    @property
    def daily_calorie_delta(self) -> int:
        """Signed daily deficit/surplus vs TDEE."""
        return self.target_calories - self.tdee

    @property
    def adjustment_label(self) -> str:
        if self.adjustment < 0:
            return "deficit"
        if self.adjustment > 0:
            return "surplus"
        return "maintenance"

    def macro_percentages(self) -> dict[str, float]:
        total = self.macro_calorie_total
        if total <= 0:
            return {"Protein": 0.0, "Fat": 0.0, "Carbs": 0.0}
        return {
            "Protein": round(self.protein_cal / total * 100, 1),
            "Fat": round(self.fat_cal / total * 100, 1),
            "Carbs": round(self.carb_cal / total * 100, 1),
        }

    def protein_per_lb(self, weight_lbs: float) -> float:
        return round(self.protein_g / weight_lbs, 2) if weight_lbs else 0.0


# ============================================================
#  ORCHESTRATION
# ============================================================

def build_plan(profile: ClientProfile, fat_carb_balance: int = 50) -> NutritionPlan:
    """Run the full pipeline for a profile at a given slider position."""
    bmr = calculate_bmr_mifflin(
        profile.age, profile.weight_lbs, profile.feet, profile.inches, profile.gender
    )
    tdee = round(bmr * get_tdee_multiplier(profile.activity_level))

    intensity = profile.fat_loss_type if profile.primary_goal == "Fat Loss" else None
    target_calories, adjustment = calculate_target_calories(
        tdee, profile.primary_goal, intensity
    )

    protein_g = calculate_protein(
        profile.primary_goal, profile.weight_lbs, profile.goal_weight_lbs
    )

    fat_pct = fat_pct_from_slider(fat_carb_balance)
    fat_g, carb_g = split_fat_and_carbs(target_calories, protein_g, fat_pct)

    timeframe = estimate_timeframe(
        profile.weight_lbs, profile.goal_weight_lbs, profile.primary_goal
    )

    plan = NutritionPlan(
        bmr=bmr,
        tdee=tdee,
        target_calories=target_calories,
        adjustment=adjustment,
        protein_g=protein_g,
        fat_g=fat_g,
        carb_g=carb_g,
        fat_pct=fat_pct,
        timeframe=timeframe,
    )
    plan.warnings = collect_warnings(profile, plan)
    return plan


def collect_warnings(profile: ClientProfile, plan: NutritionPlan) -> list[str]:
    """Non-blocking advisories for the trainer's professional judgment."""
    warnings: list[str] = []

    if plan.carb_g < 0:
        warnings.append(
            f"**Carbohydrates calculated below zero ({plan.carb_g}g).** Protein and fat "
            f"targets exceed total calories. Slide toward **Carbs** to reduce fat, or "
            f"revisit the calorie target."
        )
    elif plan.carb_g < LOW_CARB_WARNING_THRESHOLD_G:
        warnings.append(
            f"**Carbohydrates are very low ({plan.carb_g}g).** Below "
            f"{LOW_CARB_WARNING_THRESHOLD_G}g, most clients report reduced training "
            f"performance. Consider sliding toward **Carbs**."
        )

    if plan.target_calories < plan.bmr:
        warnings.append(
            f"**Target calories ({plan.target_calories}) fall below estimated BMR "
            f"({plan.bmr:.0f}).** Review before issuing this plan."
        )

    ppl = plan.protein_per_lb(profile.weight_lbs)
    if ppl > 1.5:
        warnings.append(
            f"**Protein is {ppl}g per lb of current bodyweight** — higher than the "
            f"typical 0.7–1.2g/lb working range."
        )

    if plan.timeframe and plan.timeframe[2] > 78:
        warnings.append(
            f"**Estimated timeframe is {plan.timeframe[2]} weeks.** Long horizons "
            f"usually benefit from staged targets rather than one continuous phase."
        )

    return warnings


def validate_profile(profile: ClientProfile) -> list[str]:
    """Blocking validation. Returns a list of error strings; empty means valid."""
    errors: list[str] = []
    goal = profile.primary_goal

    if goal in LOSS_GOALS and profile.goal_weight_lbs >= profile.weight_lbs:
        errors.append("Goal weight must be **lower** than current weight for Fat Loss.")

    if goal in GAIN_GOALS and profile.goal_weight_lbs <= profile.weight_lbs:
        errors.append(f"Goal weight must be **higher** than current weight for {goal}.")

    delta = abs(profile.goal_weight_lbs - profile.weight_lbs)
    if goal in (LOSS_GOALS | GAIN_GOALS) and delta > 150:
        errors.append(
            f"Goal weight differs from current weight by {delta:.0f} lbs. "
            "Please confirm both entries."
        )

    if goal == "Muscle Gain" and delta > 40:
        errors.append(
            f"A {delta:.0f} lb muscle gain target is outside a realistic single phase. "
            "Consider a staged goal."
        )

    return errors
