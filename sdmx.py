import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Title of the app
st.title("SDMX Codelist Registry")
st.sidebar.title("Options")

# API endpoint
API_ENDPOINT = "https://stats-nsi-stable.pacificdata.org/rest/codelist?detail=allstubs"

# Function to fetch and parse XML data from the API
@st.cache_data
def fetch_codelists_from_xml():
    try:
        # Fetch XML data from the API
        response = requests.get(API_ENDPOINT)
        response.raise_for_status()
        xml_content = response.content
        
        # Parse the XML data
        root = ET.fromstring(xml_content)
        codelist_data = []

        # Iterate over each <Codelist> in the XML
        for codelist in root.findall(".//structure:Codelist", namespaces={
            "structure": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
            "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
        }):
            codelist_id = codelist.attrib.get("id", "Unknown ID")
            agency_id = codelist.attrib.get("agencyID", "Unknown Agency")
            version = codelist.attrib.get("version", "Unknown Version")
            is_final = codelist.attrib.get("isFinal", "Unknown").lower() == "true"
            structure_url = codelist.attrib.get("structureURL", "Unknown URL")

            # Extract names in different languages
            names = {}
            for name_elem in codelist.findall(".//common:Name", namespaces={
                "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
            }):
                lang = name_elem.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "unknown")
                names[lang] = name_elem.text

            # Add data to the list
            codelist_data.append({
                "Codelist ID": codelist_id,
                "Agency ID": agency_id,
                "Version": version,
                "Is Final": is_final,
                "Structure URL": structure_url,
                "Name (en)": names.get("en", "N/A"),
                "Name (fr)": names.get("fr", "N/A"),
            })

        # Convert to DataFrame
        return pd.DataFrame(codelist_data)

    except ET.ParseError as e:
        st.error(f"Error parsing XML: {e}")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from API: {e}")
        return pd.DataFrame()

# Function to fetch individual codelist details
def fetch_codelist_detail(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching codelist from {url}: {e}")
        return None

# Function to extract codelist items from XML
def parse_codelist_items(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []

        # Iterate over <Code> elements
        for code in root.findall(".//structure:Code", namespaces={
            "structure": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
            "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
        }):
            code_id = code.attrib.get("id", "Unknown Code")
            names = {}
            for name_elem in code.findall(".//common:Name", namespaces={
                "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
            }):
                lang = name_elem.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "unknown")
                names[lang] = name_elem.text

            items.append({
                "Code ID": code_id,
                "Name (en)": names.get("en", "N/A"),
                "Name (fr)": names.get("fr", "N/A"),
            })

        # Convert to DataFrame
        return pd.DataFrame(items)

    except ET.ParseError as e:
        st.error(f"Error parsing codelist XML: {e}")
        return pd.DataFrame()

# Function to create PDF
def create_pdf(dataframe):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    text = c.beginText(50, 750)
    text.setFont("Helvetica", 10)

    # Add content to the PDF
    text.textLine("Codelist Details")
    text.textLine("-" * 50)
    for _, row in dataframe.iterrows():
        text.textLine(f"Code ID: {row['Code ID']}")
        text.textLine(f"Name (en): {row['Name (en)']}")
        text.textLine(f"Name (fr): {row['Name (fr)']}")
        text.textLine("")

    c.drawText(text)
    c.save()
    buffer.seek(0)
    return buffer

# Main logic
if "codelists_df" not in st.session_state:
    st.session_state.codelists_df = pd.DataFrame()

# Sidebar option to fetch API data
if st.sidebar.button("Fetch Codelists from API"):
    with st.spinner("Fetching codelists..."):
        st.session_state.codelists_df = fetch_codelists_from_xml()

# Display the codelists
if not st.session_state.codelists_df.empty:
    st.header("Codelists from API")
    st.dataframe(st.session_state.codelists_df)

    # Allow selection of a specific codelist for browsing
    st.subheader("Browse Individual Codelists")
    selected_codelist_id = st.selectbox(
        "Select a Codelist to View Details:",
        options=st.session_state.codelists_df["Codelist ID"].tolist(),
        format_func=lambda x: f"{x} - {st.session_state.codelists_df[st.session_state.codelists_df['Codelist ID'] == x]['Name (en)'].values[0]}"
    )

    # Trigger the display only when a selection is made
    if selected_codelist_id:
        # Fetch the corresponding Structure URL
        codelist_row = st.session_state.codelists_df[st.session_state.codelists_df["Codelist ID"] == selected_codelist_id]
        codelist_url = codelist_row["Structure URL"].values[0]

        st.write(f"**Selected Codelist URL**: {codelist_url}")

        # Fetch the codelist detail
        with st.spinner(f"Fetching details for {selected_codelist_id}..."):
            codelist_detail_xml = fetch_codelist_detail(codelist_url)

        if codelist_detail_xml:
            st.subheader("Codelist Details")
            codelist_items_df = parse_codelist_items(codelist_detail_xml)
            st.dataframe(codelist_items_df)

            # Download options
            st.download_button(
                label="Download Codelist as XML",
                data=codelist_detail_xml,
                file_name=f"{selected_codelist_id}.xml",
                mime="application/xml"
            )

            csv_buffer = io.StringIO()
            codelist_items_df.to_csv(csv_buffer, index=False, encoding="ISO-8859-1")
            st.download_button(
                label="Download Codelist as CSV",
                data=csv_buffer.getvalue().encode("ISO-8859-1"),
                file_name=f"{selected_codelist_id}.csv",
                mime="text/csv"
            )

            pdf_buffer = create_pdf(codelist_items_df)
            st.download_button(
                label="Download Codelist as PDF",
                data=pdf_buffer,
                file_name=f"{selected_codelist_id}.pdf",
                mime="application/pdf"
            )
else:
    st.info("Click the 'Fetch Codelists from API' button to load codelists.")
