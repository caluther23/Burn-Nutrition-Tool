"""Verify the refactor preserves the original math exactly."""
import itertools
import sys
sys.path.insert(0, '/home/claude/app')

from nutrition_core import (
    calculate_bmr_mifflin, get_tdee_multiplier, calculate_target_calories,
    calculate_protein, fat_pct_from_slider, split_fat_and_carbs,
    estimate_timeframe, ACTIVITY_MULTIPLIERS, GOALS, FAT_LOSS_INTENSITIES,
)

# ---------- ORIGINAL implementations, verbatim ----------
def orig_bmr(age, weight_lbs, hf, hi, gender):
    wk = weight_lbs / 2.20462
    hc = (hf * 30.48) + (hi * 2.54)
    if gender == "Male":
        b = (10*wk) + (6.25*hc) - (5*age) + 5
    else:
        b = (10*wk) + (6.25*hc) - (5*age) - 161
    return round(b, 1)

def orig_goal_adj(goal):
    return {"Fat Loss": -0.20, "Muscle Gain": 0.10, "Body Recomposition": -0.05,
            "Maintenance": 0.0, "Reverse Diet": 0.05}.get(goal, 0.0)

def orig_target_cal(tdee, goal, flt):
    if goal == "Fat Loss":
        if flt == "Low": return round(tdee*0.90)
        elif flt == "Moderate": return round(tdee*0.85)
        else: return round(tdee*0.80)
    return round(tdee * (1 + orig_goal_adj(goal)))

def orig_protein(goal, cw, gw):
    if goal == "Fat Loss": return round(round(gw*1.1, 1))
    elif goal in ["Muscle Gain", "Reverse Diet"]: return round(round(cw*0.9, 1))
    else: return round(round(cw*1.0, 1))

def orig_display_macros(target_calories, protein_g, balance):
    """Original DISPLAY path (the slider path that actually drove output)."""
    protein_cal = protein_g * 4
    remaining_cal = target_calories - protein_cal
    fat_pct = 0.40 - (balance/100)*0.15
    fat_g = round((target_calories*fat_pct)/9, 1)
    fat_cal = fat_g*9
    carb_g = round((remaining_cal - fat_cal)/4, 1)
    return fat_g, carb_g

def orig_timeframe(cw, gw, goal):
    d = abs(cw - gw)
    if goal == "Fat Loss": w = d/0.75
    elif goal == "Muscle Gain": w = d/0.4
    else: return None
    return int(w//4.345), int((w % 4.345)*7), round(w, 1)

# ---------- Sweep ----------
ages = [16, 25, 40, 65, 90]
weights = [110.0, 150.0, 185.5, 240.0, 320.0]
heights = [(4,11),(5,4),(5,10),(6,3),(7,0)]
genders = ["Male", "Female"]
activities = list(ACTIVITY_MULTIPLIERS.keys())

bmr_fail = tdee_fail = cal_fail = prot_fail = tf_fail = 0
n = 0
for age, w, (hf,hi), g in itertools.product(ages, weights, heights, genders):
    a = orig_bmr(age, w, hf, hi, g)
    b = calculate_bmr_mifflin(age, w, hf, hi, g)
    if a != b: bmr_fail += 1
    for act in activities:
        t_o = round(a * {"Sedentary (little to no exercise)":1.2,
            "Lightly Active (light exercise 1-3 days/week)":1.375,
            "Moderately Active (moderate exercise 3-5 days/week)":1.55,
            "Very Active (hard exercise 6-7 days/week)":1.725,
            "Super Active (very hard exercise + physical job)":1.9}[act])
        t_n = round(b * get_tdee_multiplier(act))
        if t_o != t_n: tdee_fail += 1
        for goal in GOALS:
            flts = FAT_LOSS_INTENSITIES if goal == "Fat Loss" else [None]
            for flt in flts:
                c_o = orig_target_cal(t_o, goal, flt)
                c_n, _ = calculate_target_calories(t_n, goal, flt)
                if c_o != c_n: cal_fail += 1
                for gw in [w-30, w+20]:
                    p_o = orig_protein(goal, w, gw)
                    p_n = calculate_protein(goal, w, gw)
                    if p_o != p_n: prot_fail += 1
                    if orig_timeframe(w, gw, goal) != estimate_timeframe(w, gw, goal):
                        tf_fail += 1
                    n += 1

print(f"Combinations tested: {n:,}")
print(f"BMR mismatches:      {bmr_fail}")
print(f"TDEE mismatches:     {tdee_fail}")
print(f"Calorie mismatches:  {cal_fail}")
print(f"Protein mismatches:  {prot_fail}")
print(f"Timeframe mismatch:  {tf_fail}")

# ---------- Slider mapping (INTENTIONALLY CHANGED - item 1) ----------
print("\nFat % of total calories by slider position:")
print(f"{'slider':>7} | {'OLD':>6} | {'NEW':>6}")
for s in [0, 25, 50, 75, 100]:
    old = 0.40 - (s/100)*0.15
    new = fat_pct_from_slider(s)
    print(f"{s:>7} | {old*100:>5.1f}% | {new*100:>5.1f}%")

# Verify carbs still absorb remainder correctly (structure unchanged)
tc, pg = 2000, 165
for s in [0, 50, 100]:
    fo, co = orig_display_macros(tc, pg, s)
    fn, cn = split_fat_and_carbs(tc, pg, fat_pct_from_slider(s))
    print(f"\nslider={s}: OLD fat {fo}g carb {co}g | NEW fat {fn}g carb {cn}g")
    print(f"   NEW macro cal total: {pg*4 + fn*9 + cn*4:.0f} (target {tc})")
