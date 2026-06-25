import streamlit as st
import pandas as pd

# ==========================================
# SECTION 1: APP CONFIGURATION & APP CONSTANTS
# ==========================================
st.set_page_config(
    page_title="Jupiter Ed Attendance Analytics", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏫 Jupiter Ed Attendance Analytics Dashboard")
st.markdown("---")

# Data source configurations
FILE_ID = "1e2KWmYSvt5sw38q5Rp6PrJ-QfepetWrQ"
GDRIVE_URL = f"https://docs.google.com/uc?export=download&id={FILE_ID}"


# ==========================================
# SECTION 2: DATA INGESTION & CLEANING LAYER
# ==========================================
@st.cache_data
def load_and_clean_data(url):
    """
    Fetches raw CSV from Google Drive and enforces data types 
    matching the validated 10-column schema.
    """
    df = pd.read_csv(url)
    
    # Enforce clean data types for reliable analysis
    df['StudentID'] = df['StudentID'].astype(str).str.strip()
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df['Period'] = df['Period'].astype(str).str.strip()
    df['Type'] = df['Type'].astype(str).str.strip()
    df['GradeLevel'] = df['GradeLevel'].astype(str).str.strip()
    
    return df

# Run the ingestion layer
with st.spinner("Streaming and processing 45,000+ attendance records..."):
    try:
        df_jupiter = load_and_clean_data(GDRIVE_URL)
    except Exception as e:
        st.error(f"❌ Data ingestion failed: {e}")
        st.stop()


# ==========================================
# SECTION 3: ANALYTICS & LOGIC ENGINE
# ==========================================

# --- LOGIC 1: SINGLE-PERIOD SNIPERS ---
# Isolate unexcused absences
unexcused_df = df_jupiter[df_jupiter['Type'].str.lower().str.startswith('un', na=False)]

# Group by student and class to find repeat absence patterns across the 2 days
sniper_groups = unexcused_df.groupby(
    ['StudentID', 'Name', 'Period', 'CourseSectionNum', 'Teacher']
).size().reset_index(name='Times_Missed')

# Filter for kids who missed the EXACT same class on both days
pattern_cutters = sniper_groups[sniper_groups['Times_Missed'] >= 2].sort_values(by='Period')


# --- LOGIC 2: TOTAL ABSENCE LEADERBOARD ---
# Filter out "Present" records to isolate all types of absences/tardies
absences_only_df = df_jupiter[df_jupiter['Attendance'].str.lower() != 'present']

# Create cross-tabulation to get total counts, broken down by type
leaderboard = pd.crosstab(
    index=[absences_only_df['StudentID'], absences_only_df['Name']],
    columns=absences_only_df['Type']
).reset_index()

# Dynamically find columns that represent unexcused vs excused
unex_cols = [c for c in leaderboard.columns if c.lower().startswith('un')]
ex_cols = [c for c in leaderboard.columns if not c.lower().startswith('un') and c体育 not in ['StudentID', 'Name']]

# Sum up total absences
leaderboard['Unexcused Absences'] = leaderboard[unex_cols].sum(axis=1)
leaderboard['Excused/Other Absences'] = leaderboard[ex_cols].sum(axis=1)
leaderboard['Total Absences'] = leaderboard['Unexcused Absences'] + leaderboard['Excused/Other Absences']

# Sort leaderboard by highest total absences down
leaderboard = leaderboard.sort_values(by='Total Absences', ascending=False)


# ==========================================
# SECTION 4: USER INTERFACE & SIDEBAR FILTERS
# ==========================================

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🎯 Dashboard Filters")

all_grades = sorted(df_jupiter['GradeLevel'].dropna().unique())
selected_grades = st.sidebar.multiselect("Filter by Grade Level", options=all_grades)

# Apply grade filters globally to our datasets if selected
if selected_grades:
    students_in_grade = df_jupiter[df_jupiter['GradeLevel'].isin(selected_grades)]['StudentID']
    pattern_cutters = pattern_cutters[pattern_cutters['StudentID'].isin(students_in_grade)]
    leaderboard = leaderboard[leaderboard['StudentID'].isin(students_in_grade)]

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Deans can use the search feature inside the tables or select dropdowns to audit specific students.")


# --- MAIN DISPLAY UI ---

# High-Level Metric Cards
st.subheader("📊 System Overview Metrics")
metric_col1, metric_col2, metric_col3 = st.columns(3)
with metric_col1:
    st.metric(label="Total Rows Analyzed", value=f"{len(df_jupiter):,}")
with metric_col2:
    st.metric(label="Total Non-Present Events", value=f"{len(absences_only_df):,}")
with metric_col3:
    st.metric(label="Identified Pattern Cutters", value=f"{pattern_cutters['StudentID'].nunique()}")

st.markdown("---")

# Layout: Two columns for the Core Analytics Tables
col_left, col_right = st.columns(2)

with col_left:
    st.header("🏆 Absence Leaderboard")
    st.write("Students ranked by highest accumulated total absences over 2 days:")
    st.dataframe(
        leaderboard[['StudentID', 'Name', 'Unexcused Absences', 'Excused/Other Absences', 'Total Absences']], 
        use_container_width=True,
        hide_index=True
    )

with col_right:
    st.header("🚨 Single-Period Snipers")
    st.write("Students missed the *exact same class period* on both days:")
    st.dataframe(
        pattern_cutters[['StudentID', 'Name', 'Period', 'CourseSectionNum', 'Teacher']], 
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# --- NEW FEATURE: STUDENT DETAIL DRILL-DOWN ---
st.header("🔍 Student Deep-Dive Profile Audit")
st.write("Select or search a student below to instantly pull their complete 2-day attendance history.")

# Create an easy search label array: "LastName, FirstName (ID: 12345)"
student_list = (leaderboard['Name'] + " (ID: " + leaderboard['StudentID'] + ")").tolist()

if student_list:
    selected_student_label = st.selectbox("Search Student Profile:", options=["-- Select a Student --"] + student_list)
    
    if selected_student_label != "-- Select a Student --":
        # Extract the Student ID from the label string
        target_id = selected_student_label.split("(ID: ")[1].replace(")", "").strip()
        
        # Filter raw data for just this student
        student_history = df_jupiter[df_jupiter['StudentID'] == target_id].sort_values(by=['Date', 'Period'])
        
        st.subheader(f"📋 Attendance Log for {selected_student_label}")
        
        # Display the custom interactive data log for this student
        st.dataframe(
            student_history[['Date', 'Period', 'CourseSectionNum', 'Attendance', 'Type', 'Teacher']],
            use_container_width=True,
            hide_index=True
    )
else:
    st.info("No students available to audit based on your sidebar filters.")
