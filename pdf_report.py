"""
pdf_report.py
-------------
Branded two-page PDF generation for the Client Nutrition Report.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib.utils import ImageReader

from nutrition_core import ClientProfile, NutritionPlan

# ---- Burn Boot Camp palette ----
BRAND_BLUE = colors.HexColor("#00B2E2")
DEEP_NAVY = colors.HexColor("#0A3D55")
LIGHT_GREY = colors.HexColor("#F4FBFE")
MID_GREY = colors.HexColor("#4A6472")
BORDER_GREY = colors.HexColor("#BEE9F7")

LOGO_PATH = Path(__file__).resolve().parent / "burn_boot_camp_logo.png"
LOGO_TARGET_WIDTH = 2.3 * inch


def _logo_flowable() -> Optional[Image]:
    """Load the logo at its true aspect ratio. Returns None if unavailable."""
    if not LOGO_PATH.exists():
        return None
    try:
        reader = ImageReader(str(LOGO_PATH))
        native_w, native_h = reader.getSize()
        height = LOGO_TARGET_WIDTH * (native_h / native_w)
        return Image(str(LOGO_PATH), width=LOGO_TARGET_WIDTH, height=height)
    except Exception:
        return None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "RTitle", parent=base["Heading1"], fontSize=22, leading=26,
            textColor=DEEP_NAVY, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "RSubtitle", parent=base["Normal"], fontSize=10,
            textColor=MID_GREY, spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "RHeading", parent=base["Heading2"], fontSize=12.5, leading=15,
            textColor=BRAND_BLUE, spaceBefore=9, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "RBody", parent=base["Normal"], fontSize=10, leading=14,
            textColor=DEEP_NAVY,
        ),
        "small": ParagraphStyle(
            "RSmall", parent=base["Normal"], fontSize=8.5, leading=11,
            textColor=MID_GREY,
        ),
        "cell": ParagraphStyle(
            "RCell", parent=base["Normal"], fontSize=9.5, leading=12.5,
            textColor=DEEP_NAVY,
        ),
        "bignum": ParagraphStyle(
            "RBigNum", parent=base["Normal"], fontSize=19, leading=22,
            textColor=DEEP_NAVY, alignment=TA_CENTER,
        ),
        "biglabel": ParagraphStyle(
            "RBigLabel", parent=base["Normal"], fontSize=7.5, leading=10,
            textColor=MID_GREY, alignment=TA_CENTER,
        ),
    }


def _metric_row(items: list[tuple[str, str]], s: dict, accent_last: bool = True) -> Table:
    """A row of boxed metric cards."""
    cells = []
    for label, value in items:
        cells.append([
            Paragraph(value, s["bignum"]),
            Paragraph(label.upper(), s["biglabel"]),
        ])

    inner = [Table(c, colWidths=[2.05 * inch]) for c in
             [[[cell[0]], [cell[1]]] for cell in cells]]
    for t in inner:
        t.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

    outer = Table([inner], colWidths=[2.2 * inch] * len(items))
    style = [
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.75, BORDER_GREY),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if accent_last:
        style += [
            ("BACKGROUND", (-1, 0), (-1, -1), BRAND_BLUE),
            ("BOX", (-1, 0), (-1, -1), 0.75, BRAND_BLUE),
        ]
    outer.setStyle(TableStyle(style))
    return outer


def _macro_bar(plan: NutritionPlan) -> Optional[Table]:
    """Horizontal proportional bar showing macro calorie split."""
    pcts = plan.macro_percentages()
    total = sum(pcts.values())
    if total <= 0:
        return None

    full_width = 6.9 * inch
    order = [("Protein", DEEP_NAVY), ("Fat", BRAND_BLUE), ("Carbs", colors.HexColor("#B5E7F7"))]

    widths, labels, style = [], [], []
    for idx, (name, color) in enumerate(order):
        pct = pcts[name]
        if pct <= 0:
            continue
        widths.append(full_width * pct / 100.0)
        text_hex = "#FFFFFF" if name != "Carbs" else "#0A3D55"
        labels.append(Paragraph(
            f'<font color="{text_hex}" size="8"><b>{name} {pct:.0f}%</b></font>',
            ParagraphStyle("bar", alignment=TA_CENTER, fontSize=8, leading=10),
        ))
        style.append(("BACKGROUND", (idx, 0), (idx, 0), color))

    if not widths:
        return None

    bar = Table([labels], colWidths=widths, rowHeights=[0.28 * inch])
    bar.setStyle(TableStyle(style + [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return bar


def _info_table(rows: list[tuple[str, str]], s: dict) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", s["cell"]), Paragraph(v, s["cell"])] for k, v in rows]
    t = Table(data, colWidths=[1.6 * inch, 5.3 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER_GREY),
    ]))
    return t


def _page_furniture(canvas, doc):
    """Footer drawn on every page."""
    canvas.saveState()
    canvas.setStrokeColor(BORDER_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(0.6 * inch, 0.58 * inch, letter[0] - 0.6 * inch, 0.58 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(0.6 * inch, 0.42 * inch, "Burn Boot Camp  •  Client Nutrition Report")
    canvas.drawRightString(letter[0] - 0.6 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_why_text(profile: ClientProfile, plan: NutritionPlan) -> str:
    """Goal-aware explanation shared by the app, the PDF, and the email draft."""
    goal = profile.primary_goal
    pct_of_tdee = round(plan.target_calories / plan.tdee * 100) if plan.tdee else 100

    if goal == "Fat Loss" and profile.fat_loss_type:
        return (
            f"We calculated your BMR ({plan.bmr:.0f} cal) and estimated your daily "
            f"expenditure at {plan.tdee} cal. For a <b>{profile.fat_loss_type}</b> fat loss "
            f"approach, calories are set at <b>{pct_of_tdee}% of your TDEE</b> — a daily "
            f"deficit of about {abs(plan.daily_calorie_delta)} calories. Protein is anchored "
            f"to your goal weight to help protect lean mass while you are in a deficit."
        )
    if goal == "Muscle Gain":
        return (
            f"We calculated your BMR ({plan.bmr:.0f} cal) and estimated your daily "
            f"expenditure at {plan.tdee} cal, then applied a controlled surplus of about "
            f"{abs(plan.daily_calorie_delta)} calories per day. This supports muscle growth "
            f"while limiting unnecessary fat gain. Protein is set from your current bodyweight "
            f"to supply the raw material for new tissue."
        )
    if goal == "Reverse Diet":
        return (
            f"We calculated your BMR ({plan.bmr:.0f} cal) and estimated your daily "
            f"expenditure at {plan.tdee} cal. Calories are then raised gradually — about "
            f"{abs(plan.daily_calorie_delta)} above your estimate — to help restore energy "
            f"and metabolic rate after a period of dieting, without a sharp rebound."
        )
    if goal == "Body Recomposition":
        return (
            f"We calculated your BMR ({plan.bmr:.0f} cal) and estimated your daily "
            f"expenditure at {plan.tdee} cal, then applied a small deficit of about "
            f"{abs(plan.daily_calorie_delta)} calories. Paired with consistent resistance "
            f"training and high protein, this supports losing fat and building muscle at "
            f"the same time."
        )
    return (
        f"We calculated your BMR ({plan.bmr:.0f} cal) and estimated your daily expenditure "
        f"at {plan.tdee} cal. Your calories are set at maintenance to support training "
        f"performance and long-term consistency without driving weight change."
    )


MEMBER_GUIDE = [
    ("BMR — Basal Metabolic Rate",
     "The energy your body uses at complete rest: breathing, circulation, temperature "
     "regulation, brain function. It is the floor of your daily needs before any activity."),
    ("TDEE — Total Daily Energy Expenditure",
     "Your BMR plus everything else — training, walking, daily life, and digesting food. "
     "It is the best estimate of what you actually burn in a full day, and it is the number "
     "your calorie target is built from."),
    ("Protein — 4 calories per gram",
     "Preserves and builds muscle, drives recovery, and is the most filling of the three "
     "macros. It is set first because it has the least room to compromise. Sources: chicken, "
     "lean beef, fish, eggs, Greek yogurt, cottage cheese, whey, tofu, lentils."),
    ("Fat — 9 calories per gram",
     "Supports hormone production, brain health, and absorption of vitamins A, D, E, and K. "
     "The most calorie-dense macro, so small measuring errors add up fast. Sources: olive "
     "oil, avocado, nuts, seeds, whole eggs, salmon."),
    ("Carbohydrates — 4 calories per gram",
     "Your primary training fuel. Carbs refill muscle glycogen, which powers hard efforts "
     "and repeat sets. Cutting them too low usually shows up as flat, sluggish workouts. "
     "Sources: rice, potatoes, oats, fruit, beans, whole grains."),
    ("How to use these numbers",
     "Treat them as a starting point, not a prescription. Track consistently for two to "
     "three weeks, then judge by real feedback — bodyweight trend, training performance, "
     "hunger, sleep, energy — and adjust from there. Hitting your targets roughly right "
     "most days beats hitting them perfectly for four days and then quitting."),
]


def generate_pdf(profile: ClientProfile, plan: NutritionPlan,
                 trainer_name: str = "", include_member_guide: bool = True) -> io.BytesIO:
    """Build the report and return a seek(0) BytesIO buffer."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=0.6 * inch, leftMargin=0.6 * inch,
        topMargin=0.5 * inch, bottomMargin=0.75 * inch,
        title=f"Nutrition Report - {profile.client_name or 'Client'}",
        author="Burn Boot Camp",
        subject="Client Nutrition Report",
    )
    s = _styles()
    story = []

    # ---------- Header ----------
    logo = _logo_flowable()
    if logo:
        story.append(logo)
    else:
        story.append(Paragraph(
            "<b>BURN BOOT CAMP</b>",
            ParagraphStyle("LogoFallback", fontSize=15, textColor=BRAND_BLUE, spaceAfter=2),
        ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Client Nutrition Report", s["title"]))

    meta = f"Generated {datetime.date.today().strftime('%B %d, %Y')}"
    if trainer_name.strip():
        meta += f"  •  Prepared by {trainer_name.strip()}"
    story.append(Paragraph(meta, s["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2.5, color=BRAND_BLUE, spaceAfter=10))

    # ---------- Client details ----------
    story.append(Paragraph("Client Profile", s["heading"]))
    goal_line = profile.primary_goal
    if profile.primary_goal == "Fat Loss" and profile.fat_loss_type:
        goal_line += f" — {profile.fat_loss_type} intensity"

    rows = [
        ("Name", profile.client_name or "—"),
        ("Age / Gender", f"{profile.age} · {profile.gender}"),
        ("Height", profile.height_display),
        ("Weight", f"{profile.weight_lbs:g} lbs → goal {profile.goal_weight_lbs:g} lbs"),
        ("Activity", profile.activity_level),
        ("Primary Goal", goal_line),
    ]
    if plan.timeframe:
        months, days, weeks = plan.timeframe
        rows.append(("Est. Timeframe", f"~{months} months, {days} days ({weeks:g} weeks)"))
    story.append(_info_table(rows, s))

    # ---------- Energy ----------
    story.append(Paragraph("Daily Energy Targets", s["heading"]))
    story.append(_metric_row([
        ("BMR", f"{plan.bmr:.0f}"),
        ("Est. TDEE", f"{plan.tdee}"),
        ("Daily Target", f"{plan.target_calories}"),
    ], s))

    delta = plan.daily_calorie_delta
    if delta != 0:
        word = "below" if delta < 0 else "above"
        story.append(Spacer(1, 5))
        story.append(Paragraph(
            f"That is <b>{abs(delta)} calories {word}</b> the estimated daily expenditure "
            f"(~{abs(delta) * 7:,} calories per week).", s["small"]))

    # ---------- Macros ----------
    story.append(Paragraph("Macronutrient Targets", s["heading"]))
    story.append(_metric_row([
        ("Protein", f"{plan.protein_g}g"),
        ("Fat", f"{plan.fat_g:g}g"),
        ("Carbs", f"{plan.carb_g:g}g"),
    ], s, accent_last=False))
    story.append(Spacer(1, 8))

    bar = _macro_bar(plan)
    if bar:
        story.append(bar)
        story.append(Spacer(1, 5))

    story.append(Paragraph(
        f"Calories from macros: {plan.macro_calorie_total:,.0f}  •  "
        f"Protein {plan.protein_per_lb(profile.weight_lbs)}g per lb of current bodyweight",
        s["small"]))

    # ---------- Reasoning ----------
    story.append(Paragraph("Why These Numbers", s["heading"]))
    story.append(Paragraph(build_why_text(profile, plan), s["body"]))

    if profile.client_notes.strip():
        story.append(Paragraph("Trainer Notes", s["heading"]))
        note = profile.client_notes.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>")
        story.append(Paragraph(note, s["body"]))

    # ---------- Disclaimer ----------
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER_GREY, spaceAfter=5))
    story.append(Paragraph(
        "<i>This report provides general educational guidance based on evidence-based "
        "nutrition principles. It is not medical or dietetic advice and does not replace "
        "care from a physician or registered dietitian. Clients with medical conditions, "
        "who are pregnant or nursing, or who take prescription medication should consult "
        "their healthcare provider before changing their nutrition.</i>", s["small"]))

    # ---------- Page 2 ----------
    if include_member_guide:
        story.append(PageBreak())
        story.append(Paragraph("Understanding Your Plan", s["title"]))
        story.append(Paragraph("A plain-English guide to the numbers on page one.", s["subtitle"]))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=2.5, color=BRAND_BLUE, spaceAfter=8))

        guide_heading = ParagraphStyle(
            "GuideHeading", parent=s["heading"], fontSize=11.5,
            spaceBefore=7, spaceAfter=2,
        )
        guide_body = ParagraphStyle(
            "GuideBody", parent=s["body"], fontSize=9.5, leading=12.5,
        )
        for heading, text in MEMBER_GUIDE:
            story.append(KeepTogether([
                Paragraph(heading, guide_heading),
                Paragraph(text, guide_body),
            ]))

        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER_GREY, spaceAfter=5))
        story.append(Paragraph(
            "Questions about anything here? Bring them to your next session — that is "
            "exactly what your trainer is for.", s["small"]))

    doc.build(story, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    buffer.seek(0)
    return buffer
