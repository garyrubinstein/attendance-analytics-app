import streamlit as st
import pandas as pd

st.set_page_config(page_title="Data Connection Debugger", layout="wide")
st.title("⚙️ Jupiter Ed File Connection Debugger")
st.write("This tool verifies that Streamlit can talk to Google Drive and inspects the raw file structure.")

# 1. Change the URL structure to use the direct file download endpoint
FILE_ID = "1e2KWmYSvt5sw38q5Rp6PrJ-QfepetWrQ"
gdrive_url = f"https://docs.google.com/uc?export=download&id={FILE_ID}"

# Display the download URL we are testing
st.info(f"Targeting URL: {gdrive_url}")

@st.cache_data
def load_raw_data():
    # Load the file completely raw with no cleanup to see what Jupiter actually exported
    df = pd.read_csv(gdrive_url)
    return df

# Attempt to load the data
with st.spinner("Attempting to stream file from Google Drive..."):
    try:
        df_raw = load_raw_data()
        st.success("✅ Connection Successful! Data pulled from Google Drive.")
    except Exception as e:
        st.error("❌ Connection Failed.")
        st.subheader("Error Details:")
        st.code(str(e))
        st.warning("Troubleshooting step: Double-check that 'Anyone with the link can view' is enabled for this file in your Google Drive.")
        st.stop()

# --- DEBUG INFO WINDOWS ---

st.header("📊 File Metrics")
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Total Rows Detected", value=f"{len(df_raw):,}")
with col2:
    st.metric(label="Total Columns Detected", value=len(df_raw.columns))

# 1. Inspect the Column Headers
st.header("📋 Column Headers Inspection")
st.write("These are the exact column text strings found in your file. Check for typos or extra spaces:")
columns_list = list(df_raw.columns)
st.code(str(columns_list))

# 2. Inspect Data Types and Missing Values
st.header("🔬 Data Schema & Completeness")
st.write("This shows what format Pandas thinks your data is, and if any rows have empty values.")

# Build a quick summary dataframe of the columns
debug_summary = pd.DataFrame({
    "Data Type": df_raw.dtypes.astype(str),
    "Non-Null Count": df_raw.count(),
    "Missing Values": df_raw.isnull().sum()
})
st.dataframe(debug_summary, use_container_width=True)

# 3. Preview the Raw Rows
st.header("👀 Raw Data Preview (First 20 Rows)")
st.write("This is a direct look at the first 20 rows inside the memory dataframe:")
st.dataframe(df_raw.head(20), use_container_width=True)
