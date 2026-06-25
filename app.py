import streamlit as st
import pandas as pd

# ==========================================
# SECTION 1: APP CONFIGURATION & APP CONSTANTS
# ==========================================
st.set_page_config(
    page_title="Attendance Analytics", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏫 Jupiter Ed Attendance Analytics")
st.markdown("---")

# Data source configurations
FILE_ID = "1e2KWmYSvt5sw38q5Rp6PrJ-QfepetWrQ"
GDRIVE_URL = f"https://docs.google.com/uc?export=download&id={FILE_ID}"


# ==========================================
# SECTION 2: DATA INGESTION & CLEANING LAYER
# ==========================================
@st.cache_data
def load_and_clean_data(url):
    # skip_blank_lines=True ensures that trailing empty rows at the bottom 
    # of the Jupiter export don't crash the parser
    df = pd.read_csv(url, skip_blank_lines=True)
    
    # Strip any accidental whitespace from the column headers themselves
    df.columns = df.columns.str.strip()
    
    # Enforce clean data types based on your exact working headers
    df['StudentID'] = df['StudentID'].astype(str).str.strip()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    df['Period'] = df['Period'].astype(str).str.strip()
    df['Type'] = df['Type'].astype(str).str.strip()
    df['GradeLevel'] = df['GradeLevel'].astype(str).str.strip()
    df['Attendance'] = df['Attendance'].astype(str).str.strip()
    
    return df

with st.spinner("Streaming attendance records from Google Drive..."):
    try:
        df_jupiter = load_and_clean_data(GDRIVE_URL)
    except Exception as e:
        st.error(f"❌ Data ingestion failed: {e}")
        st.stop()


# ==========================================
# SECTION 3: ANALYTICS & LOGIC ENGINE
# ==========================================

# 1. Filter out "Present" records to isolate all types of absences/tardies
absences_only_df = df_jupiter[df_jupiter['Attendance'].str.lower() != 'present'].copy()

# 2. Create cross-tabulation to get total counts per student
leaderboard = pd.crosstab(
    index=[absences_only_df['StudentID'], absences_only_df['Name']],
    columns=absences_only_df['Type']
).reset_index()

# Dynamically find columns that represent unexcused vs excused marks
unex_cols = [c for c in leaderboard.columns if c.lower().startswith('un')]
ex_cols = [c for c in leaderboard.columns if not c.lower().startswith('un') and c not in ['StudentID', 'Name']]

# Sum up total absences safely
leaderboard['Unex'] = leaderboard[unex_cols].sum(axis=1)
leaderboard['Ex/Other'] = leaderboard[ex_cols].sum(axis=1)
leaderboard['Total Absences'] = leaderboard['Unex'] + leaderboard['Ex/Other']

# Sort leaderboard by highest total absences first
leaderboard = leaderboard.sort_values(by='Total Absences', ascending=False)


# ==========================================
# SECTION 4: USER INTERFACE & DRILL-DOWN
# ==========================================

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎯 Filter Options")
all_grades = sorted(df_jupiter['GradeLevel'].dropna().unique())
selected_grades = st.sidebar.multiselect("Filter by Grade Level", options=all_grades)

if selected_grades:
    grade_ids = df_jupiter[df_jupiter['GradeLevel'].isin(selected_grades)]['StudentID'].unique()
    leaderboard = leaderboard[leaderboard['StudentID'].isin(grade_ids)]

# --- MAIN LEADERBOARD (Full Width) ---
st.header("🏆 Absence Leaderboard")
st.write("Ranking students by total accumulated absences (Excused + Unexcused) over the 2-day period.")

# Displaying Total Absences FIRST as requested
st.dataframe(
    leaderboard[['Total Absences', 'StudentID', 'Name', 'Unex', 'Ex/Other']], 
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# --- STUDENT DETAIL DRILL-DOWN ---
st.header("🔍 Student Deep-Dive Profile Audit")
st.write("Select a student to see exactly which periods they missed and a summary of their cutting habits.")

student_options = (leaderboard['Name'] + " (ID: " + leaderboard['StudentID'] + ")").tolist()

if student_options:
    selected_student_label = st.selectbox("Search/Select Student:", options=["-- Select a Student --"] + student_options)
    
    if selected_student_label != "-- Select a Student --":
        # Extract ID
        target_id = selected_student_label.split("(ID: ")[1].replace(")", "").strip()
        
        # Pull data just for this student
        student_history = df_jupiter[df_jupiter['StudentID'] == target_id].sort_values(by=['Date', 'Period'])
        student_absences = absences_only_df[absences_only_df['StudentID'] == target_id]

        # UI Layout for Drill-Down
        col_summary, col_log = st.columns([1, 2])

        with col_summary:
            st.subheader("📍 Absences by Period")
            period_counts = student_absences.groupby('Period').size().reset_index(name='Times Missed')
            st.dataframe(period_counts, hide_index=True, use_container_width=True)
            
            total_missed = period_counts['Times Missed'].sum()
            st.info(f"**Total Missed Classes:** {total_missed}")

        with col_log:
            st.subheader("📅 Chronological Log")
            st.dataframe(
                student_history[['Date', 'Period', 'CourseSectionNum', 'Attendance', 'Type', 'Teacher']],
                use_container_width=True,
                hide_index=True
            )
else:
    st.info("Select a grade from the sidebar to populate the list.")
