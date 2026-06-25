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

# 1. Isolate unexcused absences
# (Slices the data to look at rows where 'Type' starts with 'un' or 'Un')
unexcused_df = df_jupiter[df_jupiter['Type'].str.lower().str.startswith('un', na=False)]

# 2. Calculate the Single-Period Sniper logic
# Groups by student and specific class to find repeat absence patterns across the 2 days
sniper_groups = unexcused_df.groupby(
    ['StudentID', 'Name', 'Period', 'CourseSectionNum', 'Teacher']
).size().reset_index(name='Times_Missed')

# Filter for kids who missed the EXACT same class on both days
pattern_cutters = sniper_groups[sniper_groups['Times_Missed'] >= 2].sort_values(by='Period')


# ==========================================
# SECTION 4: USER INTERFACE & SIDEBAR FILTERS
# ==========================================

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🎯 Dashboard Filters")
st.sidebar.write("Use these options to narrow down the target list.")

# Grade Level Filter
all_grades = sorted(df_jupiter['GradeLevel'].dropna().unique())
selected_grades = st.sidebar.multiselect("Filter by Grade Level", options=all_grades)

# Apply filter to our final analytics array if selected
if selected_grades:
    # Check which students belong to the selected grades
    students_in_grade = df_jupiter[df_jupiter['GradeLevel'].isin(selected_grades)]['StudentID']
    pattern_cutters = pattern_cutters[pattern_cutters['StudentID'].isin(students_in_grade)]

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** This dashboard dynamically handles your 45k data export completely in-memory for the deans.")


# --- MAIN DISPLAY UI ---

# High-Level Metric Cards
st.subheader("📊 System Overview Metrics")
metric_col1, metric_col2, metric_col3 = st.columns(3)

with metric_col1:
    st.metric(label="Total Rows Analyzed", value=f"{len(df_jupiter):,}")
with metric_col2:
    st.metric(label="Total Unexcused Absence Cuts", value=f"{len(unexcused_df):,}")
with metric_col3:
    st.metric(label="Identified Pattern Cutters (2/2 Days)", value=f"{pattern_cutters['StudentID'].nunique()}")

st.markdown("---")

# Main Interactive Data Table
st.header("🚨 Target Flag: Single-Period Snipers")
st.write("Students marked **Unexcused Absent** for the *exact same class period* on both days:")

if not pattern_cutters.empty:
    st.dataframe(
        pattern_cutters[['StudentID', 'Name', 'Period', 'CourseSectionNum', 'Teacher']], 
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No students match this cutting profile under the selected filters.")
