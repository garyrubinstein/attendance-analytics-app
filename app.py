import streamlit as st
import pandas as pd
import math
import gdown
import os

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

# Your live, verified Google Drive Folder ID
FOLDER_ID = "16HLYelRNBvw3rcon9ADRElpPrn5mB_6Q" 


# ==========================================
# SECTION 2: DATA INGESTION & CLEANING LAYER
# ==========================================
@st.cache_data(ttl=3600)  # Caches data for 1 hour to keep it snappy, then re-scans the folder
def load_and_stitch_folder(folder_id):
    all_dataframes = []
    ingested_files_log = []
    
    try:
        # Fixed: Removed the command-line keyword 'remaining_ok' to resolve the exception
        files = gdown.download_folder(id=folder_id, quiet=True)
        
        if not files:
            st.error("⚠️ **Folder Error:** No files found in the Google Drive folder. Ensure your CSV files are dropped inside.")
            st.stop()
            
        # Loop through every file that was downloaded into the container
        for file in files:
            if file.endswith('.csv'):
                # Read the individual CSV file safely
                df_chunk = pd.read_csv(file, skip_blank_lines=True, on_bad_lines='skip')
                df_chunk.columns = df_chunk.columns.str.strip()
                
                # Verify this file actually belongs to the dataset structure
                if 'StudentID' in df_chunk.columns:
                    all_dataframes.append(df_chunk)
                    ingested_files_log.append({
                        "File Name": os.path.basename(file),
                        "Rows Found": len(df_chunk),
                        "Columns Found": len(df_chunk.columns)
                    })
                    
    except Exception as e:
        st.error(f"❌ Critical Folder Ingestion Failure: {e}")
        st.stop()

    if not all_dataframes:
        st.error("⚠️ **Data Alignment Error:** Found files in the folder, but none contained a valid 'StudentID' column.")
        st.stop()
        
    # Stitch all separate CSV files together into one giant master DataFrame
    master_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Enforce clean data types over the compiled million-row matrix
    master_df['StudentID'] = master_df['StudentID'].astype(str).str.strip()
    master_df['Date'] = pd.to_datetime(master_df['Date'], errors='coerce').dt.date
    master_df['Period'] = master_df['Period'].astype(str).str.strip()
    master_df['Type'] = master_df['Type'].astype(str).str.strip()
    master_df['GradeLevel'] = master_df['GradeLevel'].astype(str).str.strip()
    master_df['Attendance'] = master_df['Attendance'].astype(str).str.strip()
    
    return master_df, "Stitched Folder Streamer (Fixed)", ingested_files_log

with st.spinner("Scanning Google Drive folder and compiling all attendance exports..."):
    df_jupiter, active_parser, file_diagnostics = load_and_stitch_folder(FOLDER_ID)


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
# SECTION 4: USER INTERFACE & DRILL-DOWN (WITH PAGINATION)
# ==========================================

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎯 Filter Options")
all_grades = sorted(df_jupiter['GradeLevel'].dropna().unique())
selected_grades = st.sidebar.multiselect("Filter by Grade Level", options=all_grades)

if selected_grades:
    grade_ids = df_jupiter[df_jupiter['GradeLevel'].isin(selected_grades)]['StudentID'].unique()
    leaderboard = leaderboard[leaderboard['StudentID'].isin(grade_ids)]

# --- PAGINATION FEATURE FOR THE LEADERBOARD ---
st.header("🏆 Absence Leaderboard")

total_students = len(leaderboard)
page_size = 20

if total_students > 0:
    total_pages = math.ceil(total_students / page_size)
    
    page_options = []
    for i in range(total_pages):
        start_rank = (i * page_size) + 1
        end_rank = min((i + 1) * page_size, total_students)
        if i == 0:
            page_options.append(f"🥇 Top 20 (Ranks 1-{end_rank})")
        else:
            page_options.append(f"📋 Ranks {start_rank}-{end_rank}")
            
    col_selector, _ = st.columns([1, 2])
    with col_selector:
        selected_page_label = st.selectbox("Select Leaderboard View window:", options=page_options)
    
    selected_page_index = page_options.index(selected_page_label)
    start_idx = selected_page_index * page_size
    end_idx = start_idx + page_size
    
    paginated_df = leaderboard.iloc[start_idx:end_idx]
    st.write(f"Showing ranks {start_idx + 1} to {min(end_idx, total_students)} out of {total_students} total flagged records.")
    
    st.dataframe(
        paginated_df[['Total Absences', 'StudentID', 'Name', 'Unex', 'Ex/Other']], 
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No records found matching current sidebar criteria.")

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


# ==========================================
# DEBUG DRAWER WITH RE-BUILT LOG AUDITOR
# ==========================================
with st.expander("🛠️ System Diagnostics & Metadata (Debug Mode)"):
    st.subheader("📂 Folder Manifest Audit")
    st.write("Below is a real-time list of individual CSV files the script successfully extracted from the Google Drive folder:")
    
    # Display individual file stats inside the debug drawer
    st.dataframe(pd.DataFrame(file_diagnostics), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("📁 Global Ingestion File Specs")
    
    col_db1, col_db2, col_db3 = st.columns(3)
    with col_db1:
        st.metric("Total Blended Rows in Memory", f"{len(df_jupiter):,}")
    with col_db2:
        st.metric("Global Column Count", len(df_jupiter.columns))
    with col_db3:
        st.metric("Absence / Tardy
