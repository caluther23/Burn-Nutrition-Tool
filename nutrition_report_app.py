"""
Burn Boot Camp — Client Nutrition Report
=======================================
Streamlit front end.

Run:  streamlit run nutrition_report_app.py

Layers:
    nutrition_core.py  -> formulas & data models (no UI)
    pdf_report.py      -> branded PDF output
    this file          -> UI only
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import streamlit as st

from nutrition_core import (
    ACTIVITY_MULTIPLIERS, FAT_LOSS_INTENSITIES, GENDERS, GOALS,
    ClientProfile, build_plan, fat_pct_from_slider, validate_profile,
)
from pdf_report import build_why_text, generate_pdf

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "burn_boot_camp_logo.png"
BASECAMP_URL = "https://3.basecamp.com/5658951/buckets/39259287/message_boards/7850300503"

BRAND_BLUE = "#00AEEF"
DEEP_NAVY = "#0B2545"

# ============================================================
#  PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Client Nutrition Report | Burn Boot Camp",
    page_icon="💪",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    .block-container {{ padding-top: 2.2rem; max-width: 900px; }}

    .bbc-title {{
        font-size: 2.4rem; font-weight: 800; color: {DEEP_NAVY};
        letter-spacing: -0.02em; margin: 0.2rem 0 0.1rem 0; line-height: 1.1;
    }}
    .bbc-sub {{
        font-size: 1.0rem; color: #5A6B7B; margin-bottom: 1.2rem;
    }}
    .section-header {{
        font-size: 1.2rem; font-weight: 700; color: {DEEP_NAVY};
        margin-top: 1.8rem; margin-bottom: 0.7rem;
        border-bottom: 3px solid {BRAND_BLUE}; padding-bottom: 0.35rem;
    }}
    .stButton>button, .stDownloadButton>button, .stLinkButton>a {{
        border-radius: 8px; font-weight: 600; border: none;
    }}
    div[data-testid="stForm"] .stButton>button {{
        background-color: {BRAND_BLUE}; color: white; padding: 0.6rem 1.5rem;
    }}
    div[data-testid="stForm"] .stButton>button:hover {{
        background-color: #0090c7; color: white;
    }}
    div[data-testid="stMetric"] {{
        background: #F5F9FC; border: 1px solid #DCE7EF;
        border-radius: 10px; padding: 0.85rem 0.9rem;
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 1.55rem; color: {DEEP_NAVY};
    }}
    div[data-testid="stMetricLabel"] p {{
        font-size: 0.78rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.04em; color: #64748B;
    }}
    .macro-bar {{
        display: flex; width: 100%; height: 34px; border-radius: 7px;
        overflow: hidden; margin: 0.4rem 0 0.3rem 0;
        font-size: 0.78rem; font-weight: 700;
    }}
    .macro-seg {{
        display: flex; align-items: center; justify-content: center;
        color: #fff; white-space: nowrap; overflow: hidden;
    }}
    .disclaimer {{
        font-size: 0.83rem; color: #6B7280; font-style: italic;
        border-left: 3px solid #DCE7EF; padding: 0.5rem 0 0.5rem 0.85rem;
        margin-top: 1.5rem;
    }}
    @media print {{
        [data-testid="stSidebar"], [data-testid="stToolbar"],
        .stButton, .stDownloadButton, .stLinkButton {{ display: none !important; }}
        .block-container {{ max-width: 100% !important; padding-top: 0 !important; }}
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
#  STATE HELPERS
# ============================================================

def get_profile() -> ClientProfile | None:
    data = st.session_state.get("profile_data")
    return ClientProfile.from_dict(data) if data else None


def store_profile(profile: ClientProfile) -> None:
    st.session_state["profile_data"] = profile.to_dict()


def clear_all() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ============================================================
#  SIDEBAR
# ============================================================

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("### Report Settings")

    trainer_name = st.text_input(
        "Trainer name", value=st.session_state.get("trainer_name", ""),
        placeholder="Appears on the PDF", key="trainer_name",
    )
    include_guide = st.checkbox(
        "Include member education page in PDF", value=True,
        help="Adds a second page explaining BMR, TDEE, and each macro in plain English.",
    )

    st.divider()
    st.markdown("### Load a Saved Client")
    uploaded = st.file_uploader("Client profile (.json)", type=["json"],
                                label_visibility="collapsed")
    if uploaded is not None:
        try:
            loaded = ClientProfile.from_dict(json.load(uploaded))
            store_profile(loaded)
            st.session_state["prefill"] = loaded.to_dict()
            st.success(f"Loaded {loaded.client_name or 'client'}.")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            st.error(f"Could not read that file: {exc}")

    st.divider()
    st.caption(
        "Reports are generated in your browser session. Nothing is stored on a server. "
        "Refreshing the page clears all client data."
    )


# ============================================================
#  HEADER
# ============================================================

head_l, head_r = st.columns([3, 1], vertical_alignment="center")
with head_l:
    st.markdown('<div class="bbc-title">Client Nutrition Report</div>', unsafe_allow_html=True)
    st.markdown('<div class="bbc-sub">Evidence-based calorie and macronutrient planning</div>',
                unsafe_allow_html=True)
with head_r:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)


# ============================================================
#  INPUT FORM
# ============================================================

pre = st.session_state.get("prefill", {})


def _pv(key, default):
    """Prefill value, falling back to the default when missing or null."""
    value = pre.get(key, default)
    return default if value is None else value


def _safe_index(options: list, value, fallback):
    """Index of value in options; falls back if the value is missing or invalid."""
    if value in options:
        return options.index(value)
    return options.index(fallback)


st.markdown('<div class="section-header">Client Information</div>', unsafe_allow_html=True)

with st.form("client_form"):
    client_name = st.text_input("Client Name (First & Last)",
                                value=_pv("client_name", ""), placeholder="e.g., John Smith")

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", 16, 90, int(_pv("age", 30)), 1)
        gender = st.selectbox("Gender", GENDERS,
                              index=_safe_index(GENDERS, _pv("gender", "Male"), "Male"))
        st.markdown("**Height**")
        h1, h2 = st.columns(2)
        with h1:
            feet = st.number_input("Feet", 4, 7, int(_pv("feet", 5)), 1)
        with h2:
            inches = st.number_input("Inches", 0, 11, int(_pv("inches", 8)), 1)

    with col2:
        weight_lbs = st.number_input("Current Weight (lbs)", 80.0, 500.0,
                                     float(_pv("weight_lbs", 180.0)), 0.1, format="%.1f")
        goal_weight_lbs = st.number_input("Goal Weight (lbs)", 80.0, 500.0,
                                          float(_pv("goal_weight_lbs", 160.0)), 0.1,
                                          format="%.1f")
        activity_options = list(ACTIVITY_MULTIPLIERS.keys())
        activity_level = st.selectbox(
            "Activity Level", activity_options,
            index=_safe_index(activity_options,
                              _pv("activity_level", activity_options[2]),
                              activity_options[2]),
        )

    g1, g2 = st.columns(2)
    with g1:
        primary_goal = st.selectbox(
            "Primary Goal", GOALS,
            index=_safe_index(GOALS, _pv("primary_goal", "Fat Loss"), "Fat Loss"))
    with g2:
        fat_loss_type = st.selectbox(
            "Fat Loss Intensity", FAT_LOSS_INTENSITIES,
            index=_safe_index(FAT_LOSS_INTENSITIES,
                              _pv("fat_loss_type", "Moderate"), "Moderate"),
            help="Low = 90% of TDEE  •  Moderate = 85%  •  Aggressive = 80%. "
                 "Only applies when Primary Goal is Fat Loss.",
        )

    client_notes = st.text_area(
        "Trainer Notes",
        value=_pv("client_notes", ""),
        placeholder="Dietary modifications, medical considerations, training schedule, "
                    "food preferences, travel weeks...",
    )

    submitted = st.form_submit_button("Generate Report", use_container_width=True)

if submitted:
    profile = ClientProfile(
        client_name=client_name.strip(), age=age, gender=gender,
        feet=feet, inches=inches, weight_lbs=weight_lbs,
        goal_weight_lbs=goal_weight_lbs, activity_level=activity_level,
        primary_goal=primary_goal,
        fat_loss_type=fat_loss_type if primary_goal == "Fat Loss" else None,
        client_notes=client_notes.strip(),
    )
    errors = validate_profile(profile)
    if errors:
        for err in errors:
            st.error(err)
    else:
        store_profile(profile)
        st.session_state.pop("prefill", None)


# ============================================================
#  RESULTS
# ============================================================

profile = get_profile()

if profile:
    st.markdown('<div class="section-header">Daily Energy Targets</div>',
                unsafe_allow_html=True)

    balance = st.session_state.get("fat_carb_slider", 50)
    plan = build_plan(profile, balance)

    e1, e2, e3 = st.columns(3)
    e1.metric("BMR", f"{plan.bmr:,.0f} cal", help="Mifflin-St Jeor estimate at rest.")
    e2.metric("Estimated TDEE", f"{plan.tdee:,} cal",
              help="BMR × activity multiplier.")
    e3.metric(
        "Daily Target", f"{plan.target_calories:,} cal",
        delta=f"{plan.daily_calorie_delta:+,} vs TDEE" if plan.daily_calorie_delta else "Maintenance",
        delta_color="off",
    )

    if plan.daily_calorie_delta:
        word = "deficit" if plan.daily_calorie_delta < 0 else "surplus"
        st.caption(
            f"Weekly {word}: **{abs(plan.daily_calorie_delta) * 7:,} calories** "
            f"(~{abs(plan.daily_calorie_delta) * 7 / 3500:.2f} lbs of theoretical "
            f"tissue change per week)."
        )

    # ---------- Macro balance ----------
    st.markdown('<div class="section-header">Macronutrient Targets</div>',
                unsafe_allow_html=True)

    st.markdown("**Fat / Carb Balance**")
    sl1, sl2, sl3 = st.columns([1, 8, 1])
    sl1.markdown("**🥑 Fat**")
    with sl2:
        st.slider("Fat / Carb Balance", 0, 100, 50, 5,
                  key="fat_carb_slider", label_visibility="collapsed")
    sl3.markdown("**🍚 Carbs**")

    st.caption(
        f"Fat is set at **{plan.fat_pct * 100:.0f}% of total calories** "
        f"(centered = 30%, range 20–40%). Protein is fixed by goal; carbohydrates "
        f"take the remainder."
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Protein", f"{plan.protein_g}g",
              help=f"{plan.protein_per_lb(profile.weight_lbs)}g per lb of current bodyweight")
    m2.metric("Fat", f"{plan.fat_g:g}g", help=f"{plan.fat_cal:,.0f} calories")
    m3.metric("Carbs", f"{plan.carb_g:g}g", help=f"{plan.carb_cal:,.0f} calories")

    pcts = plan.macro_percentages()
    if sum(pcts.values()) > 0 and plan.carb_g >= 0:
        st.markdown(
            f"""<div class="macro-bar">
            <div class="macro-seg" style="width:{pcts['Protein']}%;background:{DEEP_NAVY};">
                Protein {pcts['Protein']:.0f}%</div>
            <div class="macro-seg" style="width:{pcts['Fat']}%;background:{BRAND_BLUE};">
                Fat {pcts['Fat']:.0f}%</div>
            <div class="macro-seg" style="width:{pcts['Carbs']}%;background:#9BD9F2;color:{DEEP_NAVY};">
                Carbs {pcts['Carbs']:.0f}%</div>
            </div>""",
            unsafe_allow_html=True,
        )
    st.caption(f"Total from macros: **{plan.macro_calorie_total:,.0f} calories**")

    # ---------- Warnings ----------
    for warning in plan.warnings:
        st.warning(warning)

    # ---------- Timeframe ----------
    if plan.timeframe:
        months, days, weeks = plan.timeframe
        st.markdown('<div class="section-header">Goal Progress Estimate</div>',
                    unsafe_allow_html=True)
        t1, t2, t3 = st.columns(3)
        t1.metric("Goal Weight", f"{profile.goal_weight_lbs:g} lbs")
        t2.metric("Change Needed",
                  f"{abs(profile.goal_weight_lbs - profile.weight_lbs):g} lbs")
        t3.metric("Estimated Timeframe", f"{months} mo, {days} d",
                  help=f"About {weeks:g} weeks at the planned rate of change.")
        target_date = datetime.date.today() + datetime.timedelta(weeks=weeks)
        st.caption(
            f"At the planned rate, that lands around **{target_date.strftime('%B %Y')}**. "
            f"Estimates assume steady adherence; real progress is rarely linear."
        )

    # ---------- Reasoning ----------
    st.markdown('<div class="section-header">Professional Reasoning</div>',
                unsafe_allow_html=True)
    st.markdown("**Why these calories?**")
    st.markdown(build_why_text(profile, plan).replace("<b>", "**").replace("</b>", "**"))

    st.markdown("**Macro strategy**")
    anchor = "goal weight" if profile.primary_goal == "Fat Loss" else "current bodyweight"
    st.markdown(
        f"Protein is set first, from **{anchor}**, because it is the target with the least "
        f"room to compromise — it protects lean mass and drives satiety. Fat is then set as "
        f"a share of total calories to support hormone function, and carbohydrates take "
        f"whatever remains as training fuel. Use the slider to shift that fat/carb split "
        f"toward whatever the client actually eats and performs on."
    )

    GOAL_NOTES = {
        "Low": "A conservative deficit. Slower on paper, but far easier to sustain — "
               "which is usually what determines the outcome.",
        "Moderate": "A balanced deficit. Meaningful weekly progress that most clients can "
                    "hold for a full phase.",
        "Aggressive": "A larger deficit. Best for clients with more to lose, good "
                      "adherence history, and a defined end date. Watch recovery and "
                      "training quality.",
        "Muscle Gain": "A controlled surplus supports growth while limiting fat gain. "
                       "Pair with progressive overload — a surplus without a training "
                       "stimulus is just a surplus.",
        "Reverse Diet": "Calories increase gradually to restore energy, hormone function, "
                        "and metabolic rate after dieting. Expect some weight change; "
                        "that is the point.",
        "Body Recomposition": "A small deficit with high protein and consistent resistance "
                              "training. Scale weight may barely move while body "
                              "composition shifts — track photos and measurements too.",
        "Maintenance": "Calories support performance, recovery, and consistency without "
                       "pushing weight in either direction.",
    }
    key = profile.fat_loss_type if profile.primary_goal == "Fat Loss" else profile.primary_goal
    if key in GOAL_NOTES:
        st.info(GOAL_NOTES[key])

    if profile.client_notes:
        st.markdown("**Trainer notes**")
        st.markdown(f"> {profile.client_notes}")

    st.markdown(
        '<div class="disclaimer"><strong>Disclaimer:</strong> General educational guidance '
        'based on evidence-based nutrition principles. Not medical or dietetic advice. '
        'Clients with medical conditions, who are pregnant or nursing, or who take '
        'prescription medication should consult their healthcare provider before changing '
        'their nutrition.</div>',
        unsafe_allow_html=True,
    )

    # ---------- Export ----------
    st.markdown('<div class="section-header">Export &amp; Share</div>',
                unsafe_allow_html=True)

    safe_name = ("".join(c for c in profile.client_name if c.isalnum() or c in " -_")
                 .strip().replace(" ", "_") or "Client")
    today = datetime.date.today()

    x1, x2 = st.columns(2)
    with x1:
        with st.spinner("Building PDF…"):
            pdf_buffer = generate_pdf(
                profile, plan,
                trainer_name=st.session_state.get("trainer_name", ""),
                include_member_guide=include_guide,
            )
        st.download_button(
            "📄 Download PDF Report", data=pdf_buffer,
            file_name=f"Nutrition_Report_{safe_name}_{today}.pdf",
            mime="application/pdf", use_container_width=True, type="primary",
        )
    with x2:
        st.download_button(
            "💾 Save Client Profile (.json)",
            data=json.dumps(profile.to_dict(), indent=2),
            file_name=f"Profile_{safe_name}.json",
            mime="application/json", use_container_width=True,
            help="Reload later from the sidebar to regenerate or update this plan.",
        )

    macro_line = f"Protein {plan.protein_g}g | Fat {plan.fat_g:g}g | Carbs {plan.carb_g:g}g"
    why_plain = build_why_text(profile, plan).replace("<b>", "").replace("</b>", "")
    signature = st.session_state.get("trainer_name", "").strip() or "[Your Name]"

    email_body = f"""Subject: Your Personalized Nutrition Plan

Hi {profile.first_name},

Here are your nutrition targets:

Daily Calories: {plan.target_calories:,}
Macros: {macro_line}

Why these numbers:
{why_plain}

Remember, these are a starting point. We'll track how you feel and perform
over the next two to three weeks and adjust from there.

Questions? Bring them to your next session.

{signature}
Burn Boot Camp"""

    with st.expander("📋 Email draft — click the copy icon in the top-right of the box"):
        st.code(email_body, language=None)

    st.link_button("📝 Open Client Notes (Basecamp)", BASECAMP_URL,
                   use_container_width=True)

    if st.button("🗑️ Clear All Client Data", type="secondary", use_container_width=True):
        clear_all()
        st.rerun()

else:
    st.info("Fill in the client details above and select **Generate Report**.")
