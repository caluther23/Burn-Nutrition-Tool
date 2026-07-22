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
    ClientProfile, build_plan, validate_profile,
)
from pdf_report import build_why_text, generate_pdf

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "burn_boot_camp_logo.png"
BASECAMP_URL = "https://3.basecamp.com/5658951/buckets/39259287/message_boards/7850300503"

# ---- Official Burn Boot Camp palette (blue sampled directly from the logo) ----
BRAND_BLUE = "#00B2E2"   # primary brand blue
BLUE_DARK = "#0095C0"    # hover / pressed
BLUE_TINT = "#E8F8FD"    # pale fill
BLUE_LINE = "#BEE9F7"    # light borders
INK = "#0A3D55"          # dark text (11.6:1 contrast on white)
INK_SOFT = "#4A6472"     # secondary text (6.3:1 on white)
WHITE = "#FFFFFF"

ACTIVITY_OPTIONS = list(ACTIVITY_MULTIPLIERS.keys())

st.set_page_config(
    page_title="Client Nutrition Report | Burn Boot Camp",
    page_icon="💪",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    /* ---------- Base surfaces: white-dominant ---------- */
    .stApp {{ background: {WHITE}; color: {INK}; }}
    .block-container {{ padding-top: 2.0rem; max-width: 920px; }}

    section[data-testid="stSidebar"] {{
        background: {WHITE};
        border-right: 1px solid {BLUE_LINE};
    }}

    /* ---------- Force readable text everywhere ----------
       Streamlit defaults to a light-on-dark palette when the viewer's OS is in
       dark mode. .streamlit/config.toml pins the light theme; these rules are a
       fallback so labels can never render white-on-white if that file is
       missing. */
    .stApp, .stApp p, .stApp li, .stApp label, .stApp span,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    div[data-testid="stWidgetLabel"] p,
    div[data-testid="stWidgetLabel"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        color: {INK};
    }}
    /* Inputs and dropdown menus */
    input, textarea, div[data-baseweb="select"] div,
    div[data-baseweb="popover"] li, div[data-baseweb="popover"] div {{
        color: {INK} !important;
    }}
    input::placeholder, textarea::placeholder {{
        color: #94A9B4 !important; opacity: 1;
    }}
    /* Captions and help text — softer, but still 6.3:1 on white */
    .stCaption, .stCaption p,
    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p,
    small, .stApp small {{
        color: {INK_SOFT} !important;
    }}
    /* Radio / checkbox / file uploader labels */
    div[data-testid="stRadio"] label, div[data-testid="stRadio"] label p,
    div[data-testid="stCheckbox"] label, div[data-testid="stCheckbox"] label p,
    div[data-testid="stFileUploader"] label,
    div[data-testid="stFileUploaderDropzone"] span,
    div[data-testid="stFileUploaderDropzone"] div {{
        color: {INK} !important;
    }}
    /* Expander header + slider readouts */
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary p,
    .stSlider [data-testid="stTickBar"] div,
    .stSlider div[data-baseweb="slider"] div {{
        color: {INK} !important;
    }}

    /* ---------- Typography ---------- */
    .bbc-title {{
        font-size: 2.3rem; font-weight: 800; color: {INK};
        letter-spacing: -0.02em; margin: 0.1rem 0 0.15rem 0; line-height: 1.12;
    }}
    .bbc-sub {{ font-size: 1.0rem; color: {INK_SOFT}; margin-bottom: 0.6rem; }}

    .section-header {{
        font-size: 1.15rem; font-weight: 700; color: {INK};
        margin-top: 1.7rem; margin-bottom: 0.7rem;
        border-bottom: 3px solid {BRAND_BLUE}; padding-bottom: 0.35rem;
    }}
    h3, .stMarkdown h3 {{ color: {INK}; }}

    /* ---------- Buttons ---------- */
    .stButton>button, .stDownloadButton>button, .stLinkButton>a {{
        border-radius: 8px; font-weight: 600;
    }}
    .stDownloadButton>button[kind="primary"],
    .stButton>button[kind="primary"] {{
        background-color: {BRAND_BLUE}; color: {WHITE}; border: 1px solid {BRAND_BLUE};
    }}
    .stDownloadButton>button[kind="primary"]:hover,
    .stButton>button[kind="primary"]:hover {{
        background-color: {BLUE_DARK}; border-color: {BLUE_DARK}; color: {WHITE};
    }}
    .stButton>button[kind="secondary"],
    .stDownloadButton>button[kind="secondary"] {{
        background-color: {WHITE}; color: {INK}; border: 1.5px solid {BLUE_LINE};
    }}
    .stButton>button[kind="secondary"]:hover,
    .stDownloadButton>button[kind="secondary"]:hover {{
        border-color: {BRAND_BLUE}; color: {BRAND_BLUE}; background-color: {BLUE_TINT};
    }}
    .stLinkButton>a {{
        background-color: {WHITE} !important; color: {INK} !important;
        border: 1.5px solid {BLUE_LINE} !important;
    }}
    .stLinkButton>a:hover {{
        border-color: {BRAND_BLUE} !important; color: {BRAND_BLUE} !important;
        background-color: {BLUE_TINT} !important;
    }}

    /* ---------- Metric cards ---------- */
    div[data-testid="stMetric"] {{
        background: {WHITE}; border: 1.5px solid {BLUE_LINE};
        border-radius: 10px; padding: 0.8rem 0.9rem;
    }}
    div[data-testid="stMetricValue"] {{ font-size: 1.5rem; color: {INK}; }}
    div[data-testid="stMetricLabel"] p {{
        font-size: 0.76rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.05em; color: {INK_SOFT};
    }}
    /* Emphasis for the Daily Target card (3rd metric in the energy row).
       Brand blue on white is only 2.48:1, so blue is used as a border and
       tint rather than a text background — numbers stay dark and legible. */
    #energy-row + div[data-testid="stHorizontalBlock"]
        > div[data-testid="stColumn"]:nth-child(3) div[data-testid="stMetric"] {{
        background: {BLUE_TINT};
        border: 2.5px solid {BRAND_BLUE};
    }}
    div[data-testid="stMetricDelta"] svg {{ display: none; }}
    div[data-testid="stMetricDelta"] {{
        background: transparent !important;
        color: {INK_SOFT} !important;
        font-weight: 600;
    }}

    /* ---------- Inputs ---------- */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {{
        border-color: {BLUE_LINE} !important; background-color: {WHITE} !important;
    }}
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {{
        border-color: {BRAND_BLUE} !important; box-shadow: 0 0 0 1px {BRAND_BLUE} !important;
    }}
    .stSlider [data-baseweb="slider"] [role="slider"] {{
        background-color: {BRAND_BLUE} !important;
    }}

    /* ---------- Callouts ---------- */
    .bbc-card {{
        background: {BLUE_TINT}; border: 1px solid {BLUE_LINE};
        border-left: 4px solid {BRAND_BLUE}; border-radius: 8px;
        padding: 0.8rem 1rem; font-size: 0.93rem;
        margin: 0.5rem 0 0.2rem 0;
    }}
    .bbc-card, .bbc-card p, .bbc-card strong {{ color: {INK} !important; }}
    .disclaimer, .disclaimer strong {{ color: {INK_SOFT} !important; }}
    .bbc-title {{ color: {INK} !important; }}
    .bbc-sub {{ color: {INK_SOFT} !important; }}
    .section-header {{ color: {INK} !important; }}
    .macro-bar {{
        display: flex; width: 100%; height: 34px; border-radius: 7px;
        overflow: hidden; margin: 0.5rem 0 0.35rem 0;
        font-size: 0.78rem; font-weight: 700; border: 1px solid {BLUE_LINE};
    }}
    .macro-seg {{
        display: flex; align-items: center; justify-content: center;
        white-space: nowrap; overflow: hidden;
    }}
    .disclaimer {{
        font-size: 0.83rem; color: {INK_SOFT}; font-style: italic;
        border-left: 3px solid {BLUE_LINE}; padding: 0.5rem 0 0.5rem 0.85rem;
        margin-top: 1.4rem;
    }}
    .stCaption, div[data-testid="stCaptionContainer"] p {{ color: {INK_SOFT}; }}
    hr {{ border-color: {BLUE_LINE}; }}

    /* ---------- Print ---------- */
    @media print {{
        section[data-testid="stSidebar"], [data-testid="stToolbar"], header,
        .stButton, .stDownloadButton, .stLinkButton, .no-print {{ display: none !important; }}
        .block-container {{ max-width: 100% !important; padding-top: 0 !important; }}
        div[data-testid="stMetric"] {{ break-inside: avoid; }}
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
#  STATE HELPERS
# ============================================================

WIDGET_DEFAULTS = {
    "in_client_name": "",
    "in_age": 30,
    "in_gender": "Male",
    "in_feet": 5,
    "in_inches": 8,
    "in_weight_lbs": 180.0,
    "in_goal_weight_lbs": 160.0,
    "in_activity_level": ACTIVITY_OPTIONS[2],
    "in_primary_goal": "Fat Loss",
    "in_fat_loss_type": "Moderate",
    "in_client_notes": "",
}

for _key, _default in WIDGET_DEFAULTS.items():
    st.session_state.setdefault(_key, _default)


def store_profile(profile: ClientProfile) -> None:
    st.session_state["profile_data"] = profile.to_dict()


def clear_all() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def apply_profile_to_widgets(profile: ClientProfile) -> None:
    """Push a loaded profile into the live input widgets."""
    for key, value in profile.to_dict().items():
        if key == "fat_loss_type" and value is None:
            value = "Moderate"
        st.session_state[f"in_{key}"] = value


def card(text: str) -> None:
    st.markdown(f'<div class="bbc-card">{text}</div>', unsafe_allow_html=True)


# ============================================================
#  SIDEBAR
# ============================================================

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

    st.markdown("### Report Settings")
    st.text_input("Trainer name", key="trainer_name",
                  placeholder="Appears on the PDF")
    include_guide = st.checkbox(
        "Include member education page in PDF", value=True,
        help="Adds a second page explaining BMR, TDEE, and each macro in plain English.",
    )

    st.divider()
    st.markdown("### Load a Saved Client")
    uploaded = st.file_uploader("Client profile (.json)", type=["json"],
                                label_visibility="collapsed")
    if uploaded is not None:
        token = f"{uploaded.name}:{uploaded.size}"
        if st.session_state.get("_loaded_token") != token:
            try:
                loaded = ClientProfile.from_dict(json.load(uploaded))
                apply_profile_to_widgets(loaded)
                st.session_state["_loaded_token"] = token
                st.session_state["_loaded_name"] = loaded.client_name or "client"
                st.rerun()
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                st.error(f"Could not read that file: {exc}")
    if st.session_state.get("_loaded_name"):
        st.success(f"Loaded {st.session_state['_loaded_name']}.")

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

st.markdown(
    f'<hr style="border:none;border-top:3px solid {BRAND_BLUE};'
    f'margin:0.2rem 0 0.4rem 0;">', unsafe_allow_html=True)


# ============================================================
#  INPUTS  (live-reactive — no form, so the UI adapts as you type)
# ============================================================

st.markdown('<div class="section-header">Client Information</div>', unsafe_allow_html=True)

st.text_input("Client Name (First & Last)", key="in_client_name",
              placeholder="e.g., John Smith")

col1, col2 = st.columns(2)
with col1:
    st.number_input("Age", 16, 90, key="in_age", step=1)
    st.selectbox("Gender", GENDERS, key="in_gender")
    st.markdown("**Height**")
    h1, h2 = st.columns(2)
    with h1:
        st.number_input("Feet", 4, 7, key="in_feet", step=1)
    with h2:
        st.number_input("Inches", 0, 11, key="in_inches", step=1)

with col2:
    st.number_input("Current Weight (lbs)", 80.0, 500.0, key="in_weight_lbs",
                    step=0.1, format="%.1f")
    st.number_input("Goal Weight (lbs)", 80.0, 500.0, key="in_goal_weight_lbs",
                    step=0.1, format="%.1f")
    st.selectbox("Activity Level", ACTIVITY_OPTIONS, key="in_activity_level")

# --- Goal, with intensity rendered ONLY for Fat Loss ---
goal_col, intensity_col = st.columns(2)
with goal_col:
    st.selectbox("Primary Goal", GOALS, key="in_primary_goal")

selected_goal = st.session_state["in_primary_goal"]

with intensity_col:
    if selected_goal == "Fat Loss":
        st.selectbox(
            "Fat Loss Intensity", FAT_LOSS_INTENSITIES, key="in_fat_loss_type",
            help="Low = 90% of TDEE  •  Moderate = 85%  •  Aggressive = 80%",
        )

st.text_area(
    "Trainer Notes", key="in_client_notes",
    placeholder="Dietary modifications, medical considerations, training schedule, "
                "food preferences, travel weeks...",
)

profile = ClientProfile(
    client_name=st.session_state["in_client_name"].strip(),
    age=st.session_state["in_age"],
    gender=st.session_state["in_gender"],
    feet=st.session_state["in_feet"],
    inches=st.session_state["in_inches"],
    weight_lbs=st.session_state["in_weight_lbs"],
    goal_weight_lbs=st.session_state["in_goal_weight_lbs"],
    activity_level=st.session_state["in_activity_level"],
    primary_goal=selected_goal,
    fat_loss_type=(st.session_state["in_fat_loss_type"]
                   if selected_goal == "Fat Loss" else None),
    client_notes=st.session_state["in_client_notes"].strip(),
)

errors = validate_profile(profile)
for err in errors:
    st.error(err)
if errors:
    st.stop()

store_profile(profile)


# ============================================================
#  RESULTS
# ============================================================

st.markdown('<div class="section-header">Daily Energy Targets</div>'
            '<div id="energy-row"></div>', unsafe_allow_html=True)

balance = st.session_state.get("fat_carb_slider", 50)
plan = build_plan(profile, balance)

e1, e2, e3 = st.columns(3)
e1.metric("BMR", f"{plan.bmr:,.0f} cal", help="Mifflin-St Jeor estimate at rest.")
e2.metric("Estimated TDEE", f"{plan.tdee:,} cal", help="BMR × activity multiplier.")
with e3:
    st.metric(
        "Daily Target", f"{plan.target_calories:,} cal",
        delta=(f"{plan.daily_calorie_delta:+,} vs TDEE"
               if plan.daily_calorie_delta else "At maintenance"),
        delta_color="off",
    )

if plan.daily_calorie_delta:
    word = "deficit" if plan.daily_calorie_delta < 0 else "surplus"
    st.caption(
        f"Weekly {word}: **{abs(plan.daily_calorie_delta) * 7:,} calories** "
        f"(~{abs(plan.daily_calorie_delta) * 7 / 3500:.2f} lbs of theoretical tissue "
        f"change per week)."
    )

# ---------- Macros ----------
st.markdown('<div class="section-header">Macronutrient Targets</div>', unsafe_allow_html=True)

st.markdown("**Fat / Carb Balance**")
sl1, sl2, sl3 = st.columns([1, 8, 1])
sl1.markdown("**🥑 Fat**")
with sl2:
    st.slider("Fat / Carb Balance", 0, 100, 50, 5,
              key="fat_carb_slider", label_visibility="collapsed")
sl3.markdown("**🍚 Carbs**")

st.caption(
    f"Fat is set at **{plan.fat_pct * 100:.0f}% of total calories** "
    f"(centered = 30%, range 20–40%). Protein is fixed by goal; carbohydrates take "
    f"the remainder."
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
        <div class="macro-seg" style="width:{pcts['Protein']}%;background:{INK};color:#fff;">
            Protein {pcts['Protein']:.0f}%</div>
        <div class="macro-seg" style="width:{pcts['Fat']}%;background:{BRAND_BLUE};color:#fff;">
            Fat {pcts['Fat']:.0f}%</div>
        <div class="macro-seg" style="width:{pcts['Carbs']}%;background:{BLUE_TINT};color:{INK};">
            Carbs {pcts['Carbs']:.0f}%</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.caption(f"Total from macros: **{plan.macro_calorie_total:,.0f} calories**")

# ---------- Per-meal reference ----------
meals = st.radio("Meals per day", [3, 4, 5], index=0, horizontal=True,
                 key="meals_per_day",
                 help="Splits the daily targets evenly as a starting reference.")
st.caption(
    f"Roughly per meal across {meals}: **{plan.protein_g / meals:.0f}g protein · "
    f"{plan.fat_g / meals:.0f}g fat · {plan.carb_g / meals:.0f}g carbs · "
    f"{plan.target_calories / meals:,.0f} cal**"
)

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
st.markdown('<div class="section-header">Professional Reasoning</div>', unsafe_allow_html=True)
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
    "Aggressive": "A larger deficit. Best for clients with more to lose, good adherence "
                  "history, and a defined end date. Watch recovery and training quality.",
    "Muscle Gain": "A controlled surplus supports growth while limiting fat gain. Pair "
                   "with progressive overload — a surplus without a training stimulus "
                   "is just a surplus.",
    "Reverse Diet": "Calories increase gradually to restore energy, hormone function, "
                    "and metabolic rate after dieting. Expect some weight change; that "
                    "is the point.",
    "Body Recomposition": "A small deficit with high protein and consistent resistance "
                          "training. Scale weight may barely move while body composition "
                          "shifts — track photos and measurements too.",
    "Maintenance": "Calories support performance, recovery, and consistency without "
                   "pushing weight in either direction.",
}
note_key = (profile.fat_loss_type if profile.primary_goal == "Fat Loss"
            else profile.primary_goal)
if note_key in GOAL_NOTES:
    card(GOAL_NOTES[note_key])

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
st.markdown('<div class="section-header">Export &amp; Share</div>', unsafe_allow_html=True)

safe_name = ("".join(c for c in profile.client_name if c.isalnum() or c in " -_")
             .strip().replace(" ", "_") or "Client")
today = datetime.date.today()

if not profile.client_name:
    st.caption("Add a client name above to personalize the report and file names.")

x1, x2 = st.columns(2)
with x1:
    if st.button("📄 Build PDF Report", use_container_width=True, type="primary"):
        with st.spinner("Building PDF…"):
            st.session_state["pdf_bytes"] = generate_pdf(
                profile, plan,
                trainer_name=st.session_state.get("trainer_name", ""),
                include_member_guide=include_guide,
            ).getvalue()
    if st.session_state.get("pdf_bytes"):
        st.download_button(
            "⬇️ Download PDF", data=st.session_state["pdf_bytes"],
            file_name=f"Nutrition_Report_{safe_name}_{today}.pdf",
            mime="application/pdf", use_container_width=True, type="primary",
        )
with x2:
    st.download_button(
        "💾 Save Client Profile (.json)",
        data=json.dumps(profile.to_dict(), indent=2),
        file_name=f"Profile_{safe_name}.json",
        mime="application/json", use_container_width=True, type="secondary",
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

st.link_button("📝 Open Client Notes (Basecamp)", BASECAMP_URL, use_container_width=True)

if st.button("🗑️ Reset Form", type="secondary", use_container_width=True):
    clear_all()
    st.rerun()
