# Client Nutrition Report — Burn Boot Camp

Streamlit app that generates branded, client-ready nutrition reports from
BMR/TDEE calculations and goal-specific macro targets.

## Files

| File | Purpose |
|---|---|
| `nutrition_report_app.py` | Streamlit UI (run this) |
| `nutrition_core.py` | All formulas + data models. No UI code — testable in isolation. |
| `pdf_report.py` | Two-page branded PDF generation |
| `burn_boot_camp_logo.png` | Logo (must sit beside the .py files) |
| `requirements.txt` | Dependencies |
| `test_regression.py` | Proves the refactor preserves the original math |

## Run locally

```bash
pip install -r requirements.txt
streamlit run nutrition_report_app.py
```

## Deploy (Streamlit Community Cloud — free)

Push all files to a GitHub repo, then at share.streamlit.io point a new app at
`nutrition_report_app.py`. Keep the logo in the repo root next to the scripts.

## Verify the math

```bash
python test_regression.py
```

Sweeps 17,500 input combinations against the original implementations.
Expected output: 0 mismatches on BMR, TDEE, calories, protein, and timeframe.

---

## Calculations — UNCHANGED

Every formula is preserved exactly:

- **BMR** — Mifflin-St Jeor
- **TDEE** — BMR × activity multiplier (1.2 / 1.375 / 1.55 / 1.725 / 1.9)
- **Fat Loss calories** — 90% / 85% / 80% of TDEE (Low / Moderate / Aggressive)
- **Other goals** — Muscle Gain +10%, Recomp −5%, Maintenance 0%, Reverse Diet +5%
- **Protein** — Fat Loss: goal weight × 1.1 · Muscle Gain & Reverse Diet: current × 0.9 · Recomp & Maintenance: current × 1.0
- **Fat** — a percentage of **total** calories (unchanged structure)
- **Carbs** — absorb the remainder after protein and fat
- **Timeframe** — Fat Loss 0.75 lb/wk, Muscle Gain 0.40 lb/wk

## The one intentional change: slider mapping

The old slider ran fat from **40% → 25%** of total calories, putting the
centered position at **32.5%** — which silently contradicted the documented
30% baseline in `calculate_initial_macros()`.

The slider now runs **40% → 20%**, centered on **30%**:

| Slider | Old fat % | New fat % |
|---|---|---|
| 0 (all Fat) | 40.0% | 40.0% |
| 25 | 36.3% | 35.0% |
| **50 (center)** | **32.5%** | **30.0%** |
| 75 | 28.8% | 25.0% |
| 100 (all Carbs) | 25.0% | 20.0% |

Endpoints for "max fat" are identical; the center now matches the stated
baseline and the range is symmetric. To revert, edit `BASELINE_FAT_PCT` and
`FAT_PCT_SWING` in `nutrition_core.py`.

---

## Bug fixes

1. **Email draft said "fat loss" for every client.** A Muscle Gain client
   received text about a fat loss deficit. All explanation text is now
   goal-aware and generated from one function shared by the app, the PDF, and
   the email.
2. **Hardcoded `adjustment = -0.15`** no longer exists. The adjustment is
   derived from the actual TDEE factor, so displayed percentages can never
   drift from the math.
3. **Logo path was relative** — broke depending on the launch directory. Now
   resolved relative to the script file.
4. **Logo was stretched.** Forced to 2.2"×0.85" (2.59:1) against a native
   1.91:1 image. Now scaled from true dimensions.
5. **Bare `except:`** replaced with specific exception handling.
6. **"Copy Email Body" copied nothing** — it printed a code block. Now a
   labeled expander with Streamlit's built-in copy button.
7. **PDF rebuilt on every slider move** even when not downloading.
8. **Timeframe section vanished silently** for Recomp/Maintenance/Reverse.

## Additions

- **Low-carb warnings** at <50g and at negative values, plus advisories for
  sub-BMR calories, protein above 1.5g/lb, and timeframes beyond 78 weeks
- **Macro split bar** in both the app and the PDF
- **Page 2 member education guide** — plain-English BMR, TDEE, and macro
  explanations (toggleable in the sidebar)
- **Save/load client profiles** as JSON
- **Trainer name** on the report
- **Weekly deficit/surplus** and projected target date
- **Protein per lb** readout
- **Print stylesheet** — hides chrome when printing the page directly
- Escaped HTML in trainer notes, filename sanitizing, PDF metadata

## Safety note

The disclaimer now states this is not medical or dietetic advice and directs
clients with medical conditions, who are pregnant or nursing, or who take
prescription medication to their healthcare provider first. Worth keeping —
it reflects the CPT scope of practice.
