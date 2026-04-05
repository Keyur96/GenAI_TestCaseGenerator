import base64
import streamlit as st
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
import os
import re
import io

def add_bg_from_local(image_file):
    with open(image_file, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url(data:image/{"png"};base64,{encoded_string.decode()});
        background-size: cover
    }}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
    </style>
    """,
    unsafe_allow_html=True
    )
add_bg_from_local('bg.png') 

# Streamlit UI
st.set_page_config(page_title="AI Test Case Generator", layout="wide")

# Improved Prompt (VERY IMPORTANT)
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a QA engineer.

Generate test cases in STRICT structured format:

Test Case ID: TC001
Scenario: <scenario>
Steps:
1. Step one
2. Step two
Expected Result: <expected result>
Type: Positive/Negative/Edge

Repeat for multiple test cases.
"""),
    ("human", "Generate test cases for: {requirement}")
])

def clean_llm_output(text):
    # Remove unwanted intro lines
    text = re.sub(r"Here are the test cases.*?:", "", text, flags=re.IGNORECASE)

    # Remove markdown bold (**text**)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    return text.strip()


def parse_test_cases(text):
    text = clean_llm_output(text)

    # Split into test case blocks
    blocks = re.split(r"(Test Case ID:\s*TC\d+)", text)

    data = []

    for i in range(1, len(blocks), 2):
        block = blocks[i] + blocks[i+1]

        tc_id = re.search(r"Test Case ID:\s*(TC\d+)", block)
        scenario = re.search(r"Scenario:\s*(.*)", block)
        steps = re.search(r"Steps:\n(.*?)Expected Result:", block, re.DOTALL)
        expected = re.search(r"Expected Result:\s*(.*)", block)
        tc_type = re.search(r"Type:\s*(.*)", block)

        data.append({
            "Test Case ID": tc_id.group(1).strip() if tc_id else "",
            "Scenario": scenario.group(1).strip() if scenario else "",
            "Steps": steps.group(1).strip() if steps else "",
            "Expected Result": expected.group(1).strip() if expected else "",
            "Type": tc_type.group(1).strip() if tc_type else ""
        })

    return pd.DataFrame(data)

st.sidebar.title("Get model and api key details from user")
st.session_state.model = st.sidebar.text_input("Please enter groq model name : ")
st.session_state.api_key = st.sidebar.text_input("Enter groq api key : ")

os.environ["GROQ_API_KEY"] = st.session_state.api_key
model = ChatGroq(model=st.session_state.model)

chain = prompt | model

# Session state
if "output" not in st.session_state:
    st.session_state.output = ""
if "df" not in st.session_state:
    st.session_state.df = None

st.title("🤖 AI Test Case Generator")

# Input options
input_method = st.radio("Choose input method:", ["Enter Requirement", "Upload File"])

requirement_text = ""

if input_method == "Enter Requirement":
    st.subheader("Example requirement text : 'User should be able to login with email and password'")
    requirement_text = st.text_area("Enter Requirement:", height=150)

elif input_method == "Upload File":
    st.subheader("Upload Requirement File")
    uploaded_file = st.file_uploader("Upload Requirement File", type=["txt", "csv"])

    if uploaded_file:
        if uploaded_file.type == "text/plain":
            requirement_text = uploaded_file.read().decode("utf-8")
        elif uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
            requirement_text = " ".join(df.astype(str).values.flatten())

# Generate button
# if st.button("Generate Test Cases"):
#     try:
#         if requirement_text.strip() == "":
#             st.error("Please provide requirement input.")
#         else:
#             with st.spinner("Generating test cases..."):
#                 response = chain.invoke({"requirement": requirement_text})
#                 st.session_state.output = response.content
#                 st.session_state.df = parse_test_cases(st.session_state.output)
#     except Exception as exc:
#         st.error(f"Pipeline failed unexpectedly: {exc}")
#         st.stop()

if st.button("Generate Test Cases"):
    try:
        if requirement_text.strip() == "":
            st.error("Please provide requirement input.")
            st.stop()

        if not st.session_state.model or not st.session_state.api_key:
            st.error("Model name and API key are required.")
            st.stop()

        with st.spinner("Generating test cases..."):
            response = chain.invoke({"requirement": requirement_text})

            st.session_state.output = response.content
            st.session_state.df = parse_test_cases(st.session_state.output)

    except Exception as exc:
        error_msg = str(exc).lower()

        if "invalid api key" in error_msg or "authentication" in error_msg:
            st.error("🔑 Invalid API Key. Please check and try again.")

        elif "model not found" in error_msg:
            st.error("🤖 Invalid Model Name. Please verify the model.")

        elif "rate limit" in error_msg or "quota" in error_msg:
            st.error("⏳ API limit reached. Please try again later.")

        elif "timeout" in error_msg:
            st.error("🌐 Request timed out. Please retry.")

        else:
            st.error(f"⚠️ Unexpected error: {exc}")

        st.stop()

# Show RAW output
if st.session_state.output:
    st.subheader("📋 Raw Test Cases")
    st.text_area("Raw Output", st.session_state.output, height=300)

# Show structured table
if st.session_state.df is not None and not st.session_state.df.empty:
    st.subheader("📊 Structured Test Cases")
    st.dataframe(st.session_state.df)

    # Excel Export (2 sheets)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Sheet 1 - Raw
        raw_df = pd.DataFrame({"Raw Output": [st.session_state.output]})
        raw_df.to_excel(writer, sheet_name="Raw Output", index=False)

        # Sheet 2 - Structured
        st.session_state.df.to_excel(writer, sheet_name="Structured Test Cases", index=False)

    buffer.seek(0)

    st.download_button(
        label="📥 Download Excel (Raw + Structured)",
        data=buffer,
        file_name="test_cases.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
