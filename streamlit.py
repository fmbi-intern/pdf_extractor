import streamlit as st
import os
import re
import pypdfium2 as pdfium
import pandas as pd
from io import BytesIO
import zipfile
import time  # for smooth progress updates

# -------------------------------
# PDF text extraction
# -------------------------------
def extract_text_from_first_page(pdf_bytes):
    pdf = pdfium.PdfDocument(pdf_bytes)
    text_output = ""
    
    if len(pdf) > 0:
        first_page = pdf[0]  
        textpage = first_page.get_textpage()
        text_output = textpage.get_text_bounded()
        textpage.close()
    
    pdf.close()
    return text_output

# -------------------------------
# Pattern definitions
# -------------------------------
PATTERNS_TYPE_1 = {
    "Inspection": r"([^\n]+)(?=\s+Store ID and Name)",
    "Store ID and Name": r"Store ID and Name\s+([\s\S]+?)\s+Tracker",
    "Tracker": r"Tracker\s+([\s\S]+?)\s+Inspector",
    "Inspector": r"Inspector\s+([^\n]+)",
    "Project Team PIC": r"Project Team PIC\s+([^\n]+)",
    "Project Team Present": r"Project Team Present\s+([^\n]+)",
    "Contractor PIC": r"Contractor PIC\s+([^\n]+)",
    "Contractor Present": r"Contractor Present\s+([^\n]+)",
    "Issue Date": r"Issue Date\s+([^\n]+)",
    "Inspection Date": r"Inspection Date\s+([^\n]+)",
    "Report Date": r"Report Date\s+([^\n]+)",
    "Handover Date": r"Handover Date\s+([^\n]+)"
}

PATTERNS_TYPE_2 = {
    "Document No.": r"Document No\.\s+([^\n]+)",
    "Audit Title": r"Audit Title\s+([^\n]+)",
    "Site Name": r"Site Name\s+([^\n]+)",
    "Location": r"Location\s+([\s\S]+?)\s+Contractor Present",  # keep multi-line capture
    "Contractor Present": r"Contractor Present\s+([^\n]+)",
    "Contractor Name": r"Contractor Present\s+[^\n]+\s+Name\s+([^\n]+)",
    "Project PIC Present": r"Project PIC Present\s+([^\n]+)",
    "Project PIC Name": r"Project PIC Present\s+[^\n]+\s+Name\s+([^\n]+)",
    "Inspected by": r"Inspected by\s+([^\n]+)",
    "Inspection Date": r"Inspection Date\s+([^\n]+)",
    "Prepared by": r"Prepared by\s+([^\n]+)"
}

# -------------------------------
# Detect PDF type
# -------------------------------
def detect_document_type(text):
    if re.search(r"Document No\.", text):
        return "type_2"
    elif re.search(r"Store ID and Name", text):
        return "type_1"
    else:
        return None

# -------------------------------
# Extract data by type
# -------------------------------
def extract_data_by_type(text, doc_type):
    patterns = PATTERNS_TYPE_1 if doc_type == "type_1" else PATTERNS_TYPE_2
    data = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            value = " ".join(value.split())  # collapse multi-line
            data[field] = value
        else:
            data[field] = None
    data["Document Type"] = doc_type
    return data

# -------------------------------
# Streamlit app
# -------------------------------
st.set_page_config(
    page_title="PDF Inspection Data Extractor",
    layout="wide",  # this makes it full width
    initial_sidebar_state="expanded"
)

st.title("PDF Inspection Data Extractor")

uploaded_zip = st.file_uploader(
    "Upload a ZIP file containing PDFs",
    type="zip"
)

if uploaded_zip:
    all_data_type_1 = []
    all_data_type_2 = []

    with zipfile.ZipFile(uploaded_zip) as z:
        pdf_files = [f for f in z.namelist() if f.lower().endswith(".pdf")]
        total_files = len(pdf_files)

        st.write(f"Found {total_files} PDF(s) in the ZIP file.")
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, pdf_name in enumerate(pdf_files, start=1):
            status_text.text(f"Processing: {pdf_name} ({i}/{total_files})")
            try:
                pdf_bytes = z.read(pdf_name)
                text = extract_text_from_first_page(BytesIO(pdf_bytes))
                doc_type = detect_document_type(text)
                if doc_type is None:
                    st.warning(f"Unknown document type: {pdf_name}")
                    continue

                data = extract_data_by_type(text, doc_type)
                data["Source File"] = pdf_name

                if doc_type == "type_1":
                    all_data_type_1.append(data)
                else:
                    all_data_type_2.append(data)

            except Exception as e:
                st.error(f"Error processing {pdf_name}: {e}")
            
            progress_bar.progress(i / total_files)
            time.sleep(0.05)  # smooth visual update

        status_text.text("Processing complete!")
        progress_bar.empty()

    # Show preview tables and download buttons
    if all_data_type_1:
        st.subheader("Preview: Type 1 PDFs")
        df1 = pd.DataFrame(all_data_type_1)
        st.dataframe(df1)
        buffer1 = BytesIO()
        df1.to_excel(buffer1, index=False)
        buffer1.seek(0)
        st.download_button(
            "Download Type 1 Excel",
            data=buffer1,
            file_name="inspection_summary_type_1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if all_data_type_2:
        st.subheader("Preview: Type 2 PDFs")
        df2 = pd.DataFrame(all_data_type_2)
        st.dataframe(df2)
        buffer2 = BytesIO()
        df2.to_excel(buffer2, index=False)
        buffer2.seek(0)
        st.download_button(
            "Download Type 2 Excel",
            data=buffer2,
            file_name="inspection_summary_type_2.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if not all_data_type_1 and not all_data_type_2:
        st.info("No data extracted from the PDFs in the ZIP.")