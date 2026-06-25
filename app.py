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

# Your verified, public streaming web link:
GDRIVE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQkI_5b3FAWYjlvHXNhg_Z2edAc1mR1GnIc3OT1CDA6RrZRf0MzZ4GgtwOJ-ZQkFRI58FFQTuUWSmP3/pub?output=csv"


# ==========================================
# SECTION 2: DATA INGESTION & CLEANING LAYER
# ==========================================
@st.cache_data
def load_and_clean_data(url):
    # Stream the raw CSV seamlessly from the web publish endpoint
    df = pd.read_csv(url, skip_blank_lines=True, on_bad_lines='skip')
    
    # Strip any accidental whitespace from headers
    df.columns = df.columns.str.strip()
    
    # EMERGENCY CHECK: Ensure it's reading data and not an error page
    if 'StudentID' not in df.columns or df.empty:
        st.error("⚠️ **Data Stream Error:** The app could not locate the 'StudentID' column header.")
        st.stop()
        
    # Enforce clean data types for the analytics metrics
    df['StudentID'] = df['StudentID'].astype(str).str.strip()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    df['Period'] = df['Period'].astype(str).str.strip()
    df['Type'] = df['Type'].astype(str).str.strip()
    df['GradeLevel'] = df['GradeLevel'].astype(str).str.strip()
    df['Attendance'] = df['Attendance'].astype(str).str.strip()
    
    return df, "Verified Web-Published CSV Streamer"

with st.spinner("Streaming attendance records from Google Drive..."):
    try:
        df_jupiter, active_parser = load_and_clean_data(GDRIVE_URL)
    except Exception as e:
        st.error(f"❌ Structural Ingestion Failure: {e}")
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
        target_id = selected_student_label.split("(ID: ")[1].replace(")", "").strip()
        
        student_history = df_jupiter[df_jupiter['StudentID'] == target_id].sort_values(by=['Date', 'Period'])
        student_absences = absences_only_df[absences_only_df['StudentID'] == target_id]

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

st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("---")

# --- SYSTEM DIAGNOSTICS DETAILED DRAWER ---
with st.expander("🛠️ System Diagnostics & Metadata (Debug Mode)"):
    st.subheader("📁 Ingestion File Specs")
    
    col_db1, col_db2, col_db3 = st.columns(3)
    with col_db1:
        st.metric("Total Row Entries In Memory", f"{len(df_jupiter):,}")
    with col_db2:
        st.metric("Detected Column Count", len(df_jupiter.columns))
    with col_db3:
        st.metric("Absence / Tardy Events Isolated", f"{len(absences_only_df):,}")
        
    st.markdown("**Parser Status:**")
    st.code(active_parser)
    
    st.markdown("**Parsed Column Headers List:**")
    st.code(str(list(df_jupiter.columns)))
    
    st.markdown("**Data Type Verification (Schema):**")
    schema_df = pd.DataFrame({
        "Pandas Data Type": df_jupiter.dtypes.astype(str),
        "Non-Null Value Count": df_jupiter.count(),
        "Missing/Null Values": df_jupiter.isnull().sum()
    })
    st.dataframe(schema_df, use_container_width=True)
    
    st.markdown("**Raw In-Memory Head Preview (First 5 Rows):**")
    st.dataframe(df_jupiter.head(5), use_container_width=True)
