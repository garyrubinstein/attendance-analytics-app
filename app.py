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
@st.cache_data(ttl=3600)  # Standard 1 hour cache to prevent API rate limits
def load_and_stitch_folder(folder_id):
    all_dataframes = []
    folder_manifest = []  # Keeps track of EVERYTHING found in the directory
    
    try:
        # Pull everything out of the cloud target folder 
        downloaded_paths = gdown.download_folder(id=folder_id, quiet=True)
        
        if not downloaded_paths:
            return None, "Empty Folder", [{"Status": "❌ Error", "Item": "No files found or folder is private."}]
            
        for path in downloaded_paths:
            file_name = os.path.basename(path)
            
            # Diagnostic Checklist logic
            if file_name.endswith('.csv'):
                try:
                    df_chunk = pd.read_csv(path, skip_blank_lines=True, on_bad_lines='skip')
                    df_chunk.columns = df_chunk.columns.str.strip()
                    
                    if 'StudentID' in df_chunk.columns:
                        all_dataframes.append(df_chunk)
                        folder_manifest.append({
                            "File Name": file_name,
                            "Status": "✅ Successfully Stitched",
                            "Rows": len(df_chunk),
                            "Details": "Valid CSV with 'StudentID' header"
                        })
                    else:
                        folder_manifest.append({
                            "File Name": file_name,
                            "Status": "⚠️ Skipped (Bad Structure)",
                            "Rows": len(df_chunk),
                            "Details": "Missing expected 'StudentID' header column"
                        })
                except Exception as csv_err:
                    folder_manifest.append({
                        "File Name": file_name,
                        "Status": "❌ Skipped (Corrupted)",
                        "Rows": 0,
                        "Details": f"Read Error: {str(csv_err)}"
                    })
            else:
                # Catches Google Sheets, PDFs, text logs, etc.
                folder_manifest.append({
                    "File Name": file_name,
                    "Status": "ℹ️ Ignored (Wrong Extension)",
                    "Rows": 0,
                    "Details": "Not a raw .csv file format"
                })
                
    except Exception as e:
        st.error(f"❌ Critical Folder Ingestion Failure: {e}")
        st.stop()

    if not all_dataframes:
        return None, "No Valid CSVs", folder_manifest
        
    # Stitch data frames together
    master_df = pd.concat(all_dataframes, ignore_index=True)
    
    # Enforce data schemas
    master_df['StudentID'] = master_df['StudentID'].astype(str).str.strip()
    master_df['Date'] = pd.to_datetime(master_df['Date'], errors='coerce').dt.date
    master_df['Period'] = master_df['Period'].astype(str).str.strip()
    master_df['Type'] = master_df['Type'].astype(str).str.strip()
    master_df['GradeLevel'] = master_df['GradeLevel'].astype(str).str.strip()
    master_df['Attendance'] = master_df['Attendance'].astype(str).str.strip()
    
    return master_df, f"Stitched Streamer ({len(all_dataframes)} CSV files blended)", folder_manifest


# Trigger the loader
with st.spinner("Synchronizing with Google Drive folder container..."):
    df_jupiter, active_parser, folder_manifest_log = load_and_stitch_folder(FOLDER_ID)

# Handle cases where folder is readable but files aren't matching up
if df_jupiter is None:
    st.error("⚠️ **Inbound Pipeline Halted:** No valid data files could be compiled.")
    st.info("Check the **System Diagnostics** module at the bottom of the page to review the real-time manifest log analysis.")
    if st.button("🔄 Force Clear Memory & Retry Scan Now"):
        st.cache_data.clear()
        st.rerun()
    st.stop()


# ==========================================
# SECTION 3: ANALYTICS & LOGIC ENGINE
# ==========================================
absences_only_df = df_jupiter[df_jupiter['Attendance'].str.lower() != 'present'].copy()

leaderboard = pd.crosstab(
    index=[absences_only_df['StudentID'], absences_only_df['Name']],
    columns=absences_only_df['Type']
).reset_index()

unex_cols = [c for c in leaderboard.columns if c.lower().startswith('un')]
ex_cols = [c for c in leaderboard.columns if not c.lower().startswith('un') and c not in ['StudentID', 'Name']]

leaderboard['Unex'] = leaderboard[unex_cols].sum(axis=1)
leaderboard['Ex/Other'] = leaderboard[ex_cols].sum(axis=1)
leaderboard['Total Absences'] = leaderboard['Unex'] + leaderboard['Ex/Other']
leaderboard = leaderboard.sort_values(by='Total Absences', ascending=False)


# ==========================================
# SECTION 4: USER INTERFACE & DRILL-DOWN
# ==========================================

# --- SIDEBAR FILTERS & FORCE CLEAR OVERRIDE ---
st.sidebar.header("🎯 Filter Options")
all_grades = sorted(df_jupiter['GradeLevel'].dropna().unique())
selected_grades = st.sidebar.multiselect("Filter by Grade Level", options=all_grades)

if selected_grades:
    grade_ids = df_jupiter[df_jupiter['GradeLevel'].isin(selected_grades)]['StudentID'].unique()
    leaderboard = leaderboard[leaderboard['StudentID'].isin(grade_ids)]

st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Cache Management")
st.sidebar.write("Dropped a new file in Drive? Clear the temporary memory cache to force a re-scan:")
if st.sidebar.button("🧹 Force Re-Scan Drive Folder"):
    st.cache_data.clear()
    st.rerun()

# --- MAIN LEADERBOARD ---
st.header("🏆 Absence Leaderboard")
total_students = len(leaderboard)
page_size = 20

if total_students > 0:
    total_pages = math.ceil(total_students / page_size)
    page_options = [f"🥇 Top 20 (Ranks 1-{min(page_size, total_students)})"] if total_students <= page_size else [f"📋 Ranks {(i*page_size)+1}-{min((i+1)*page_size, total_students)}" for i in range(total_pages)]
    
    col_selector, _ = st.columns([1, 2])
    with col_selector:
        selected_page_label = st.selectbox("Select Leaderboard View window:", options=page_options)
    
    selected_page_index = page_options.index(selected_page_label)
    start_idx = selected_page_index * page_size
    end_idx = start_idx + page_size
    
    paginated_df = leaderboard.iloc[start_idx:end_idx]
    st.write(f"Showing ranks {start_idx + 1} to {min(end_idx, total_students)} out of {total_students} entries.")
    st.dataframe(paginated_df[['Total Absences', 'StudentID', 'Name', 'Unex', 'Ex/Other']], use_container_width=True, hide_index=True)
else:
    st.info("No records found matching current sidebar criteria.")

st.markdown("---")

# --- STUDENT DETAIL DRILL-DOWN ---
st.header("🔍 Student Deep-Dive Profile Audit")
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
            st.info(f"**Total Missed Classes:** {period_counts['Times Missed'].sum()}")
        with col_log:
            st.subheader("📅 Chronological Log")
            st.dataframe(student_history[['Date', 'Period', 'CourseSectionNum', 'Attendance', 'Type', 'Teacher']], use_container_width=True, hide_index=True)

st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# ADVANCED UPGRADED DIAGNOSTICS LOG VISUALIZER
# ==========================================
with st.expander("🛠️ System Diagnostics & Folder Ingestion Live Logs (Debug Mode)"):
    st.subheader("📡 Live Folder Manifest Audit Log")
    st.write("This table logs every individual object found inside the Google Drive folder container during the current scan execution:")
    
    # Render the new detailed check status tracking log
    st.dataframe(pd.DataFrame(folder_manifest_log), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("📊 Global Combined In-Memory Statistics")
    col_db1, col_db2, col_db3 = st.columns(3)
    with col_db1:
        st.metric("Total Blended Dataset Rows", f"{len(df_jupiter):,}" if df_jupiter is not None else "0")
    with col_db2:
        st.metric("Global Checked Columns", len(df_jupiter.columns) if df_jupiter is not None else "0")
    with col_db3:
        st.metric("Absence Incidents Extracted", f"{len(absences_only_df):,}" if df_jupiter is not None else "0")
