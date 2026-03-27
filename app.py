import csv
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import CATEGORY_ORDER, QUESTIONS
from history import get_all_assessments, get_last_assessment, save_assessment
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
    prior = get_last_assessment(org_name)
    results = calculate_results(answers, org_type=org_type)
    save_assessment(org_name, org_type, org_size, results)
    payload = build_llm_payload(org_name, org_type, org_size, results)
    report = generate_ai_report(payload)

    st.markdown("---")
    st.subheader("Results Dashboard")
    score_delta = results["overall_score"] - prior["overall_score"] if prior else None
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall Score", f"{results['overall_score']}/100",
              delta=score_delta, delta_color="normal" if score_delta else "off")
    c2.metric("Risk Level", results["risk_level"],
              delta=f"was {prior['risk_level']} on {prior['date']}" if prior and prior["risk_level"] != results["risk_level"] else None,
              delta_color="off")
    c3.metric("Unmet Controls", str(len(results["findings"])))

    if prior:
        st.subheader("Change vs Last Assessment")
        st.caption(f"Compared to {prior['date']}")
        cols = st.columns(len(results["category_scores"]))
        for col, (cat, score) in zip(cols, results["category_scores"].items()):
            prev_score = prior["category_scores"].get(cat)
            col.metric(cat, f"{score}/100", delta=score - prev_score if prev_score is not None else None)

    st.subheader("Category Scores")
    cats = list(results["category_scores"].keys())
    scores = list(results["category_scores"].values())
    radar_fig = go.Figure(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=cats + [cats[0]],
        fill="toself",
        line_color="#1f77b4",
        fillcolor="rgba(31,119,180,0.25)",
    ))
    radar_fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        margin=dict(t=20, b=20, l=40, r=40),
        height=380,
    )
    st.plotly_chart(radar_fig, use_container_width=True)

    st.subheader("Controls Traffic Light")

    def _traffic_color(answer: str) -> str:
        return {"Yes": "#d4edda", "Partially": "#fff3cd"}.get(answer, "#f8d7da")

    def _traffic_label(answer: str) -> str:
        return {"Yes": "✅ Yes", "Partially": "⚠️ Partially"}.get(answer, "🔴 " + answer)

    rows_html = ""
    for q in QUESTIONS:
        answer = answers.get(q.id, "Don't Know")
        bg = _traffic_color(answer)
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 8px">{q.category}</td>'
            f'<td style="padding:4px 8px">{q.text}</td>'
            f'<td style="padding:4px 8px;text-align:center">{_traffic_label(answer)}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;font-size:0.85rem">'
        f'<thead><tr style="background:#f0f0f0">'
        f'<th style="padding:4px 8px;text-align:left">Category</th>'
        f'<th style="padding:4px 8px;text-align:left">Control</th>'
        f'<th style="padding:4px 8px;text-align:center">Status</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

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

all_entries = get_all_assessments(org_name)
if len(all_entries) >= 2:
    st.markdown("---")
    st.subheader("Score Trend")
    labels = []
    date_counts: dict = {}
    for e in all_entries:
        d = e["date"]
        date_counts[d] = date_counts.get(d, 0) + 1
        labels.append(f"Run {date_counts[d]} ({d})")
    df = pd.DataFrame(
        [{"Overall": e["overall_score"], **e["category_scores"]} for e in all_entries],
        index=labels,
    )
    st.line_chart(df)
