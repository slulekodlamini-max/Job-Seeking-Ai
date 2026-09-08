
import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
import re

st.set_page_config(page_title="Job Seeking AI", page_icon="🤖", layout="wide")

PROFILE = {
    "name": "Your Name",
    "qualification": "Diploma in Civil Engineering — CPUT, completed 2025",
    "experience": "Work Integrated Learning at WBHO (June–December 2025)",
    "registration": "ECSA Candidate",
    "skills": "Excel, Microsoft Project, PowerPoint, PROKON, surveying, teamwork, communication, problem solving",
    "locations": "Cape Town, Western Cape; Johannesburg/Gauteng; KwaZulu-Natal; South Africa",
    "roles": "Graduate Civil Engineer, Candidate Civil Engineer, Junior Civil Engineer, Site Engineer, Graduate Site Engineer, Junior Project Engineer, Civil Engineering Technician",
}

jobs = pd.DataFrame([
    {
        "Title":"Graduate Programme 2026 (Civil Engineering)",
        "Company":"Hatch",
        "Location":"Johannesburg, Gauteng",
        "Match":72,
        "Why":"Strong graduate/engineering fit, but the listing specifies BSc/BEng Civil Engineering.",
        "Source":"Indeed",
        "URL":"https://za.indeed.com/Civil-Engineering-Graduate-jobs-in-South-Africa"
    },
    {
        "Title":"Engineering Graduates",
        "Company":"thyssenkrupp Uhde South Africa",
        "Location":"Johannesburg, Gauteng",
        "Match":78,
        "Why":"Graduate engineering opportunity; qualification requirements should be checked before applying.",
        "Source":"Indeed",
        "URL":"https://za.indeed.com/Civil-Engineering-Graduate-jobs-in-South-Africa"
    },
    {
        "Title":"Engineer",
        "Company":"SMEC",
        "Location":"Cape Town, Western Cape",
        "Match":84,
        "Why":"Civil engineering environment and Cape Town location make this worth checking.",
        "Source":"LinkedIn",
        "URL":"https://za.linkedin.com/jobs/civil-engineering-graduate-jobs"
    },
    {
        "Title":"Civil Engineer (Water)",
        "Company":"Zutari",
        "Location":"Cape Town, Western Cape",
        "Match":83,
        "Why":"Strong civil/infrastructure alignment; verify experience and qualification requirements.",
        "Source":"LinkedIn",
        "URL":"https://za.linkedin.com/jobs/civil-engineering-graduate-jobs"
    },
    {
        "Title":"Zutari Graduate Talent Community",
        "Company":"Zutari",
        "Location":"Cape Town, Western Cape",
        "Match":91,
        "Why":"Graduate talent route and strong location/discipline alignment.",
        "Source":"LinkedIn",
        "URL":"https://za.linkedin.com/jobs/civil-engineer-trainee-jobs"
    },
    {
        "Title":"Junior Project Engineer / Quantity Surveyor — Graduate Role",
        "Company":"Awnmaster / Solara / Quantum Group",
        "Location":"Cape Town, Western Cape",
        "Match":88,
        "Why":"Graduate/entry-level role and practical engineering/construction experience are relevant.",
        "Source":"Indeed",
        "URL":"https://za.indeed.com/q-graduate-civil-engineer-jobs.html"
    },
])

st.title("🤖 Job Seeking AI")
st.caption("Your personal job-search dashboard — prototype v1")

tabs = st.tabs(["🏠 Dashboard", "🔎 Jobs", "📄 CV & Cover Letter", "📋 Applications", "🎤 Interview AI", "⚙️ Profile"])

with tabs[0]:
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Jobs found", len(jobs))
    c2.metric("Strong matches", int((jobs.Match >= 80).sum()))
    c3.metric("Applications", 0)
    c4.metric("Interviews", 0)
    st.subheader("⭐ Best current matches")
    st.dataframe(jobs.sort_values("Match", ascending=False)[["Match","Title","Company","Location","Source"]], hide_index=True, use_container_width=True)
    st.info("This prototype already uses live job-search research to seed the dashboard. The next build can connect automated searches and your documents.")

with tabs[1]:
    st.subheader("🔎 Job Finder")
    min_match = st.slider("Minimum match score", 0, 100, 75)
    location = st.selectbox("Location", ["All","Cape Town","Johannesburg","Gauteng","KwaZulu-Natal","South Africa"])
    filtered = jobs[jobs.Match >= min_match]
    if location != "All":
        filtered = filtered[filtered.Location.str.contains(location, case=False, na=False)]
    for _, j in filtered.sort_values("Match", ascending=False).iterrows():
        with st.container(border=True):
            st.markdown(f"### {j.Title} — {j.Company}")
            st.write(f"**{j.Location} · Match: {j.Match}% · Source: {j.Source}**")
            st.write(j.Why)
            st.link_button("View job", j.URL)

with tabs[2]:
    st.subheader("📄 Application Document Generator")
    selected = st.selectbox("Choose a job", jobs.Title.tolist())
    j = jobs[jobs.Title == selected].iloc[0]
    name = st.text_input("Your name", "Your Name")
    if st.button("Generate tailored application pack"):
        st.markdown("### Tailored CV profile")
        st.write(f"{name} — Civil Engineering graduate with a Diploma in Civil Engineering from CPUT, practical WIL experience at WBHO, ECSA Candidate registration, and skills in engineering software, surveying, teamwork and problem solving.")
        st.markdown("### Tailored cover letter")
        st.write(f"""Dear Hiring Manager,

I am applying for the {j.Title} position at {j.Company}. I completed a Diploma in Civil Engineering at CPUT and gained practical industry experience during my Work Integrated Learning placement at WBHO. I am also registered as an ECSA Candidate.

My academic and practical background has developed my skills in civil engineering, surveying, project work, problem solving, teamwork and engineering software. I am eager to continue developing professionally and contribute to your projects.

I would appreciate the opportunity to discuss my application.

Kind regards,
{name}""")

with tabs[3]:
    st.subheader("📋 Application Tracker")
    if "applications" not in st.session_state:
        st.session_state.applications = pd.DataFrame(columns=["Date","Company","Position","Status","Notes"])
    st.dataframe(st.session_state.applications, hide_index=True, use_container_width=True)
    with st.form("add"):
        company = st.text_input("Company")
        position = st.text_input("Position")
        status = st.selectbox("Status", ["Prepared","Applied","Interview","Rejected","Offer"])
        notes = st.text_input("Notes")
        if st.form_submit_button("Add application"):
            st.session_state.applications.loc[len(st.session_state.applications)] = [str(date.today()),company,position,status,notes]
            st.rerun()

with tabs[4]:
    st.subheader("🎤 Interview AI")
    role = st.text_input("Job title", "Graduate Civil Engineer")
    if st.button("Generate interview preparation"):
        questions = [
            "Tell us about yourself and your civil engineering background.",
            "Why do you want to work for this company?",
            "Tell us about your WBHO/WIL experience.",
            "Describe a civil engineering problem you solved.",
            "Which engineering software are you comfortable using?",
            "How do you work in a multidisciplinary team?",
            "Where do you see your engineering career developing?"
        ]
        for q in questions:
            st.markdown(f"**Q: {q}**")
            st.write("AI answer: Prepare a short answer using your real experience, the STAR method, and specific technical examples.")

with tabs[5]:
    st.subheader("⚙️ Your Profile")
    for k,v in PROFILE.items():
        st.text_input(k.title(), v, key=k)
    st.success("Profile saved for this prototype session.")

st.divider()
st.caption("Prototype v1 • Human approval remains required before any application is submitted.")
