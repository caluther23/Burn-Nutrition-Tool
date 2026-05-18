import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import datetime
import os

# ====================== HELPER FUNCTIONS ======================
def calculate_bmr_mifflin(age, weight_lbs, height_feet, height_inches, gender):
    weight_kg = weight_lbs / 2.20462
    height_cm = (height_feet * 30.48) + (height_inches * 2.54)
    
    if gender == "Male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    return round(bmr, 1)

def get_tdee_multiplier(activity):
    multipliers = {
        "Sedentary (little to no exercise)": 1.2,
        "Lightly Active (light exercise 1-3 days/week)": 1.375,
        "Moderately Active (moderate exercise 3-5 days/week)": 1.55,
        "Very Active (hard exercise 6-7 days/week)": 1.725,
        "Super Active (very hard exercise + physical job)": 1.9
    }
    return multipliers.get(activity, 1.55)

def get_goal_adjustment(goal):
    adjustments = {
        "Fat Loss": -0.20,
        "Muscle Gain": 0.10,
        "Body Recomposition": -0.05,
        "Maintenance": 0.0,
        "Reverse Diet": 0.05
    }
    return adjustments.get(goal, 0.0)

def calculate_initial_macros(calories, goal, weight_lbs):
    if goal == "Fat Loss":
        protein_g = round(weight_lbs * 1.1, 1)
    elif goal in ["Muscle Gain", "Reverse Diet"]:
        protein_g = round(weight_lbs * 0.9, 1)
    else:
        protein_g = round(weight_lbs * 1.0, 1)
    
    protein_cal = protein_g * 4
    remaining_cal = calories - protein_cal
    
    fat_pct = 0.30
    fat_g = round((calories * fat_pct) / 9, 1)
    fat_cal = fat_g * 9
    carb_g = round((remaining_cal - fat_cal) / 4, 1)
    
    return round(protein_g), round(fat_g), round(carb_g)

def estimate_timeframe(current_weight, goal_weight, goal):
    weight_diff = abs(current_weight - goal_weight)
    
    if goal == "Fat Loss":
        weeks = weight_diff / 0.75
    elif goal == "Muscle Gain":
        weeks = weight_diff / 0.4
    else:
        return None
    
    months = int(weeks // 4.345)
    days = int((weeks % 4.345) * 7)
    return months, days, round(weeks, 1)

# ====================== PAGE CONFIG & THEMING ======================
st.set_page_config(
    page_title="Client Nutrition Report",
    page_icon="💪",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.6rem;
        font-weight: 700;
        color: #0077B6;
        text-align: center;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #333333;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.35rem;
        font-weight: 600;
        color: #0077B6;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
        border-bottom: 2px solid #0077B6;
        padding-bottom: 0.3rem;
    }
    .stButton>button {
        background-color: #0077B6;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #005f8a;
        color: white;
    }
    .disclaimer {
        font-size: 0.85rem;
        color: #666666;
        font-style: italic;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ====================== HEADER ======================
st.markdown('<h1 class="main-header">Client Nutrition Report</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Professional Client Nutrition Planning Tool</p>', unsafe_allow_html=True)
st.markdown("---")

# ====================== INPUT FORM ======================
st.markdown('<h2 class="section-header">Client Information</h2>', unsafe_allow_html=True)

with st.form("client_form"):
    client_name = st.text_input("Client Name (First & Last)", placeholder="e.g., John Smith")

    col1, col2 = st.columns(2)
    
    with col1:
        age = st.number_input("Age", min_value=16, max_value=90, value=30, step=1)
        gender = st.selectbox("Gender", ["Male", "Female"])
        
        st.write("**Height**")
        height_col1, height_col2 = st.columns(2)
        with height_col1:
            feet = st.number_input("Feet", min_value=4, max_value=7, value=5, step=1)
        with height_col2:
            inches = st.number_input("Inches", min_value=0, max_value=11, value=8, step=1)
    
    with col2:
        weight_lbs = st.number_input("Current Weight (lbs)", min_value=80.0, max_value=500.0, value=180.0, step=0.1, format="%.1f")
        goal_weight_lbs = st.number_input("Goal Weight (lbs)", min_value=80.0, max_value=500.0, value=160.0, step=0.1, format="%.1f")
        
        activity_level = st.selectbox(
            "Activity Level",
            [
                "Sedentary (little to no exercise)",
                "Lightly Active (light exercise 1-3 days/week)",
                "Moderately Active (moderate exercise 3-5 days/week)",
                "Very Active (hard exercise 6-7 days/week)",
                "Super Active (very hard exercise + physical job)"
            ]
        )
    
    primary_goal = st.selectbox(
        "Primary Goal",
        ["Fat Loss", "Muscle Gain", "Body Recomposition", "Maintenance", "Reverse Diet"]
    )
    
    client_notes = st.text_area(
        "Client Notes",
        placeholder="Dietary modifications, medical needs, training goals, etc.."
    )
    
    submitted = st.form_submit_button("Generate Professional Report", use_container_width=True)

# ====================== VALIDATION + SESSION STATE ======================
if submitted:
    validation_error = False

    # Fat Loss validation
    if primary_goal == "Fat Loss" and goal_weight_lbs >= weight_lbs:
        st.error("Goal weight must be lower than Current Weight for Fat Loss.")
        validation_error = True

    # Muscle Gain validation
    elif primary_goal == "Muscle Gain" and goal_weight_lbs <= weight_lbs:
        st.error("Goal weight must be higher than Current Weight for Muscle Gain.")
        validation_error = True

    # Reverse Diet validation (NEW)
    elif primary_goal == "Reverse Diet" and goal_weight_lbs <= weight_lbs:
        st.error("Goal weight must be higher than Current Weight for Reverse Diet.")
        validation_error = True

    # Only proceed if no validation errors
    if not validation_error:
        st.session_state['submitted'] = True
        st.session_state['client_name'] = client_name
        st.session_state['age'] = age
        st.session_state['gender'] = gender
        st.session_state['feet'] = feet
        st.session_state['inches'] = inches
        st.session_state['weight_lbs'] = weight_lbs
        st.session_state['goal_weight_lbs'] = goal_weight_lbs
        st.session_state['activity_level'] = activity_level
        st.session_state['primary_goal'] = primary_goal
        st.session_state['client_notes'] = client_notes

        bmr = calculate_bmr_mifflin(age, weight_lbs, feet, inches, gender)
        tdee_multiplier = get_tdee_multiplier(activity_level)
        tdee = round(bmr * tdee_multiplier)
        adjustment = get_goal_adjustment(primary_goal)
        target_calories = round(tdee * (1 + adjustment))
        initial_protein, initial_fat, initial_carbs = calculate_initial_macros(target_calories, primary_goal, weight_lbs)
        timeframe = estimate_timeframe(weight_lbs, goal_weight_lbs, primary_goal)

        st.session_state['bmr'] = bmr
        st.session_state['tdee'] = tdee
        st.session_state['target_calories'] = target_calories
        st.session_state['initial_protein'] = initial_protein
        st.session_state['initial_fat'] = initial_fat
        st.session_state['initial_carbs'] = initial_carbs
        st.session_state['timeframe'] = timeframe
        st.session_state['adjustment'] = adjustment

# ====================== DISPLAY RESULTS ======================
if st.session_state.get('submitted', False):
    client_name = st.session_state['client_name']
    age = st.session_state['age']
    gender = st.session_state['gender']
    feet = st.session_state['feet']
    inches = st.session_state['inches']
    weight_lbs = st.session_state['weight_lbs']
    goal_weight_lbs = st.session_state['goal_weight_lbs']
    primary_goal = st.session_state['primary_goal']
    client_notes = st.session_state.get('client_notes', '')
    bmr = st.session_state['bmr']
    tdee = st.session_state['tdee']
    target_calories = st.session_state['target_calories']
    initial_protein = st.session_state['initial_protein']
    initial_fat = st.session_state['initial_fat']
    initial_carbs = st.session_state['initial_carbs']
    timeframe = st.session_state['timeframe']
    adjustment = st.session_state['adjustment']

    st.markdown("---")
    st.markdown('<h2 class="section-header">Calculations</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("BMR", f"{bmr} cal")
    with col2:
        st.metric("Estimated TDEE", f"{tdee} cal")
    with col3:
        st.metric("Recommended Calories", f"{target_calories} cal")

    # ====================== FAT/CARB SLIDER ======================
    st.markdown("**Adjust Fat vs Carbs Balance**")
    st.caption("Move toward **Fat** = Higher Fat / Lower Carbs | Move toward **Carbs** = Lower Fat / Higher Carbs")

    col_fat, col_slider, col_carbs = st.columns([1, 6, 1])
    with col_fat:
        st.markdown("**Fat**")
    with col_slider:
        fat_carb_balance = st.slider(
            "Fat / Carb Balance",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
            key="fat_carb_slider",
            label_visibility="collapsed"
        )
    with col_carbs:
        st.markdown("**Carbs**")

    protein_g = initial_protein
    protein_cal = protein_g * 4
    remaining_cal = target_calories - protein_cal

    fat_pct = 0.40 - (fat_carb_balance / 100) * 0.15
    fat_g = round((target_calories * fat_pct) / 9, 1)
    fat_cal = fat_g * 9
    carb_g = round((remaining_cal - fat_cal) / 4, 1)

    st.markdown("**Final Macro Targets**")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Protein", f"{protein_g}g")
    with m2:
        st.metric("Fat", f"{fat_g}g")
    with m3:
        st.metric("Carbs", f"{carb_g}g")

    if primary_goal in ["Fat Loss", "Muscle Gain"]:
        st.markdown("**Goal Progress Estimate**")
        tf_col1, tf_col2 = st.columns(2)
        with tf_col1:
            st.metric("Goal Weight", f"{goal_weight_lbs} lbs")
        with tf_col2:
            if timeframe:
                st.metric("Estimated Timeframe", f"{timeframe[0]} months, {timeframe[1]} days")

    # ====================== RECOMMENDATIONS ======================
    st.markdown('<h2 class="section-header">Professional Recommendations & Reasoning</h2>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown("### Why These Calories?")
        st.markdown(f"""
        We calculated a **BMR** of **{bmr} cal** and estimated **TDEE** at **{tdee} cal**. 
        For the goal of **{primary_goal}**, we applied a **{abs(int(adjustment*100))}% {"deficit" if adjustment < 0 else "surplus" if adjustment > 0 else "maintenance"}** 
        to create a sustainable calorie target of **{target_calories} cal** while protecting muscle mass.
        """)

        st.markdown("### Macro Strategy")
        st.markdown(f"""
        Protein is set at **{protein_g}g** to prioritize muscle retention. 
        The Fat and Carbohydrate split can be adjusted using the slider above while keeping total daily calories constant.
        """)

        if primary_goal == "Fat Loss":
            st.info("A moderate deficit combined with higher protein helps create fat loss while minimizing muscle loss and metabolic adaptation.")
        elif primary_goal == "Muscle Gain":
            st.info("A controlled surplus provides extra energy for muscle repair and growth. The slider allows personalization of fat versus carbohydrate intake based on preference.")
        elif primary_goal == "Reverse Diet":
            st.info("Gradually increasing calories while adjusting the fat-to-carb ratio helps restore metabolic rate and hormone function after a dieting phase.")
        else:
            st.info("Maintenance calories allow focus on performance, recovery, and consistency with flexible macro distribution.")

    st.markdown("""
    <div class="disclaimer">
    <strong>Disclaimer:</strong> This tool provides general educational guidance based on evidence-based nutrition principles. 
    Intended for qualified fitness professionals. Use professional judgment with each client.
    </div>
    """, unsafe_allow_html=True)

    # ====================== EXPORT & SHARE SECTION ======================
    st.markdown('<h2 class="section-header">Export & Share</h2>', unsafe_allow_html=True)

    def generate_pdf():
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                                rightMargin=0.6*inch, leftMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, 
                                     textColor=colors.HexColor('#0077B6'), alignment=TA_CENTER, spaceAfter=4)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], 
                                       fontSize=13, textColor=colors.HexColor('#0077B6'), spaceBefore=10)
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10.5, leading=14)
        
        story = []
        
        # Burn Boot Camp Logo
        logo_path = "burn_boot_camp_logo.png"
        if os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=2.2*inch, height=0.85*inch)
                logo_table = Table([[logo]], colWidths=[6.5*inch])
                logo_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT')]))
                story.append(logo_table)
            except:
                story.append(Paragraph("<b>Burn Boot Camp</b>", 
                    ParagraphStyle('LogoFallback', fontSize=14, textColor=colors.HexColor('#0077B6'), alignment=TA_LEFT, spaceAfter=6)))
        else:
            story.append(Paragraph("<b>Burn Boot Camp</b>", 
                ParagraphStyle('LogoFallback', fontSize=14, textColor=colors.HexColor('#0077B6'), alignment=TA_LEFT, spaceAfter=6)))
        
        story.append(Spacer(1, 6))
        story.append(Paragraph("Client Nutrition Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.date.today().strftime('%B %d, %Y')}", normal_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0077B6')))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph(f"<b>Client:</b> {client_name}", normal_style))
        story.append(Paragraph(f"Age: {age} &nbsp;|&nbsp; Gender: {gender} &nbsp;|&nbsp; Height: {feet}'{inches}\"", normal_style))
        story.append(Paragraph(f"Current Weight: {weight_lbs} lbs → Goal Weight: {goal_weight_lbs} lbs", normal_style))
        story.append(Paragraph(f"<b>Primary Goal:</b> {primary_goal}", normal_style))
        
        if client_notes:
            story.append(Paragraph(f"<b>Client Notes:</b> {client_notes}", normal_style))
        
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Calculations</b>", heading_style))
        story.append(Paragraph(f"BMR: {bmr} cal &nbsp;|&nbsp; TDEE: {tdee} cal", normal_style))
        story.append(Paragraph(f"<b>Recommended Daily Calories: {target_calories} cal</b>", normal_style))
        story.append(Paragraph(f"<b>Macros:</b> Protein {protein_g}g &nbsp;|&nbsp; Fat {fat_g}g &nbsp;|&nbsp; Carbs {carb_g}g", normal_style))
        
        if timeframe:
            story.append(Paragraph(f"<b>Estimated Time to Goal Weight:</b> ~{timeframe[0]} months, {timeframe[1]} days", normal_style))
        
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Why These Recommendations?</b>", heading_style))
        story.append(Paragraph(
            f"Calculated using Mifflin-St Jeor BMR and activity-based TDEE. Applied a {abs(int(adjustment*100))}% "
            f"{'deficit' if adjustment < 0 else 'surplus' if adjustment > 0 else 'maintenance'} for the goal of {primary_goal}. "
            "Fat and carbohydrate distribution was personalized using the interactive balance slider while maintaining total daily calories.", 
            normal_style))
        
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Paragraph(
            "<i>This report provides general guidance based on evidence-based nutrition principles. Use professional judgment with each client.</i>", 
            ParagraphStyle('Footer', fontSize=9, textColor=colors.grey)))
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    pdf_buffer = generate_pdf()

    # ====================== EXPORT BUTTONS ======================
    st.markdown("**Quick Actions**")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📋 Copy Email Body + Notes", use_container_width=True):
            email_body = f"""Subject: Your Personalized Nutrition Recommendations

Hi {client_name.split()[0] if client_name else 'there'},

Here is your customized nutrition plan:

**Recommended Daily Calories:** {target_calories} cal
**Macros:** Protein {protein_g}g | Fat {fat_g}g | Carbs {carb_g}g

**Why these numbers?**
We calculated your BMR and TDEE, then applied a {abs(int(adjustment*100))}% {"deficit" if adjustment < 0 else "surplus" if adjustment > 0 else "maintenance"} based on your goal of {primary_goal}. 
Protein is prioritized for muscle retention. Fat and carbs were adjusted using a balance slider while keeping total calories the same.

Please let me know if you have any questions!

Best regards,
[Your Name]"""
            st.code(email_body)
            st.success("Copied! Now click the button below to open Basecamp and paste it.")

    with col2:
        st.link_button(
            "📝 Open Client Notes (Basecamp)",
            "https://3.basecamp.com/5658951/buckets/39259287/message_boards/7850300503",
            use_container_width=True
        )

    st.download_button(
        "📄 Download PDF", 
        data=pdf_buffer, 
        file_name=f"Client_Nutrition_Report_{datetime.date.today()}.pdf", 
        mime="application/pdf", 
        use_container_width=True
    )

    if st.button("🗑️ Clear All Data", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.markdown("---")
st.caption("Professional tool for fitness coaches • Evidence-based • Client Nutrition Report")