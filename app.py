import csv
import io

import streamlit as st

from data import CATEGORY_ORDER, QUESTIONS
from report import build_llm_payload, generate_ai_report
from scoring import calculate_results

st.set_page_config(page_title="RiskLens AI", page_icon="🛡️", layout="wide")
st.title("RiskLens AI")
st.caption("Cyber risk assessment assistant for small organizations")

with st.sidebar:
    st.header("Organization Profile")
    org_name = st.text_input("Organization Name", value="Sample Organization")
    org_type = st.selectbox("Organization Type", ["Small Business", "Nonprofit", "School", "Clinic", "Startup", "Other"])
    org_size = st.selectbox("Organization Size", ["1-10 employees", "11-50 employees", "51-200 employees", "201+ employees"])
    st.markdown("---")
    st.write("Scoring bands")
    st.write("80–100: Low")
    st.write("60–79: Moderate")
    st.write("40–59: High")
    st.write("0–39: Critical")

st.subheader("Assessment Questionnaire")

if "answers" not in st.session_state:
    st.session_state.answers = {}

for category in CATEGORY_ORDER:
    with st.expander(category, expanded=True):
        for q in [x for x in QUESTIONS if x.category == category]:
            current = st.session_state.answers.get(q.id)
            options = ["Yes", "Partially", "No", "Don't Know"]
            idx = options.index(current) if current in options else None
            selection = st.radio(
                q.text,
                options=options,
                index=idx,
                horizontal=True,
                key=f"radio_{q.id}",
            )
            if selection is not None:
                st.session_state.answers[q.id] = selection

answers = st.session_state.answers

answered_count = sum(1 for q in QUESTIONS if q.id in answers)
total_count = len(QUESTIONS)
st.caption(f"{answered_count}/{total_count} answered")
if answered_count < total_count:
    st.info(f"{total_count - answered_count} question(s) not yet answered — they will be treated as \"Don't Know\".")

if st.button("Run Assessment", type="primary"):
    results = calculate_results(answers, org_type=org_type)
    payload = build_llm_payload(org_name, org_type, org_size, results)
    report = generate_ai_report(payload)

    st.markdown("---")
    st.subheader("Results Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall Score", f"{results['overall_score']}/100")
    c2.metric("Risk Level", results["risk_level"])
    c3.metric("Unmet Controls", str(len(results["findings"])))

    st.subheader("Category Scores")
    st.bar_chart(results["category_scores"])

    st.subheader("Top 3 Priority Actions")
    for idx, action in enumerate(results["top_actions"], start=1):
        with st.container(border=True):
            st.markdown(f"**{idx}. {action['category']}**")
            st.write(action["question"])
            st.write(f"Answer: {action['answer']}")
            st.write(f"Priority Score: {action['priority_score']}")
            st.write(f"Recommended Fix: {action['remediation']}")
            st.write(f"Why it matters: {action['why_it_matters']}")
            st.write(f"Framework mapping: {action['framework_map']}")

    st.subheader("AI Report")
    st.text_area("Generated Assessment Report", value=report, height=380)

    with st.expander("Structured JSON Output"):
        st.json(payload)

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["RiskLens AI — Assessment Report"])
    writer.writerow(["Organization", org_name, "Type", org_type, "Size", org_size])
    writer.writerow(["Overall Score", results["overall_score"], "Risk Level", results["risk_level"]])
    writer.writerow([])
    writer.writerow(["Category Scores"])
    writer.writerow(["Category", "Score"])
    for cat, score in results["category_scores"].items():
        writer.writerow([cat, score])
    writer.writerow([])
    writer.writerow(["All Findings"])
    writer.writerow(["#", "Category", "Question", "Answer", "Priority Score", "Remediation", "Why It Matters", "Framework Map"])
    for i, f in enumerate(results["findings"], start=1):
        writer.writerow([i, f["category"], f["question"], f["answer"], f["priority_score"], f["remediation"], f["why_it_matters"], f["framework_map"]])
    writer.writerow([])
    writer.writerow(["AI Report"])
    writer.writerow([report])

    st.download_button(
        label="Download Report as CSV",
        data=csv_buf.getvalue(),
        file_name=f"risklens_report_{org_name.replace(' ', '_')}.csv",
        mime="text/csv",
    )
