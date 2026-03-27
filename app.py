import csv
import io
import json
import os
from dataclasses import dataclass
from typing import Dict, List

from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file (if present)
load_dotenv()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -----------------------------
# Data model
# -----------------------------
@dataclass
class Question:
    id: str
    text: str
    category: str
    weight: int
    impact: float
    remediation: str
    why_it_matters: str
    framework_map: str


QUESTIONS: List[Question] = [
    Question(
        id="q1",
        text="Do all employees use multi-factor authentication for email and critical systems?",
        category="Access Control",
        weight=10,
        impact=1.5,
        remediation="Enable MFA on email, VPN, admin portals, and cloud apps for all users.",
        why_it_matters="MFA sharply reduces account-takeover risk when passwords are stolen.",
        framework_map="NIST PR.AA / CIS Control 6",
    ),
    Question(
        id="q2",
        text="Are strong unique passwords required or managed with a password manager?",
        category="Access Control",
        weight=8,
        impact=1.2,
        remediation="Enforce strong unique passwords and deploy a password manager.",
        why_it_matters="Weak or reused passwords are a common path for compromise.",
        framework_map="NIST PR.AA / CIS Control 5",
    ),
    Question(
        id="q3",
        text="Are former employees removed from systems promptly after leaving?",
        category="Access Control",
        weight=8,
        impact=1.3,
        remediation="Create an offboarding checklist that disables accounts and revokes access immediately.",
        why_it_matters="Stale accounts increase the chance of unauthorized access.",
        framework_map="NIST PR.AC / CIS Control 6",
    ),
    Question(
        id="q4",
        text="Are company laptops and desktops protected with antivirus or EDR tools?",
        category="Endpoint Security",
        weight=8,
        impact=1.2,
        remediation="Install and centrally manage endpoint protection on all company devices.",
        why_it_matters="Endpoint controls help detect malware, ransomware, and suspicious execution.",
        framework_map="NIST PR.IP / CIS Control 10",
    ),
    Question(
        id="q5",
        text="Are company devices encrypted in case they are lost or stolen?",
        category="Endpoint Security",
        weight=7,
        impact=1.2,
        remediation="Enable full-disk encryption on laptops and mobile devices.",
        why_it_matters="Encryption prevents data exposure when devices are lost, stolen, or repurposed.",
        framework_map="NIST PR.DS / CIS Control 3",
    ),
    Question(
        id="q6",
        text="Are operating systems and business software updated on a regular schedule?",
        category="Patch Management",
        weight=9,
        impact=1.3,
        remediation="Establish patching windows and track critical updates to completion.",
        why_it_matters="Unpatched systems are often exploited through known vulnerabilities.",
        framework_map="NIST PR.IP / CIS Control 7",
    ),
    Question(
        id="q7",
        text="Do you track which systems are missing critical security patches?",
        category="Patch Management",
        weight=8,
        impact=1.2,
        remediation="Maintain an asset and patch compliance inventory with exception tracking.",
        why_it_matters="You cannot remediate patch gaps reliably without visibility.",
        framework_map="NIST ID.AM / CIS Control 1, 7",
    ),
    Question(
        id="q8",
        text="Is sensitive business or customer data stored securely?",
        category="Data Protection",
        weight=8,
        impact=1.3,
        remediation="Classify sensitive data and secure it using approved storage and access controls.",
        why_it_matters="Improper storage increases exposure risk and regulatory impact.",
        framework_map="NIST PR.DS / CIS Control 3",
    ),
    Question(
        id="q9",
        text="Is access to sensitive data limited only to people who need it?",
        category="Data Protection",
        weight=7,
        impact=1.3,
        remediation="Apply least-privilege access and review permissions regularly.",
        why_it_matters="Overbroad access increases both internal misuse and breach blast radius.",
        framework_map="NIST PR.AC / CIS Control 6",
    ),
    Question(
        id="q10",
        text="Are important files and systems backed up automatically?",
        category="Backup & Recovery",
        weight=10,
        impact=1.4,
        remediation="Implement automated backups for critical data and systems.",
        why_it_matters="Backups are essential for recovery from ransomware, deletion, or outage.",
        framework_map="NIST PR.IP / CIS Control 11",
    ),
    Question(
        id="q11",
        text="Are backups tested to confirm they can actually be restored?",
        category="Backup & Recovery",
        weight=9,
        impact=1.4,
        remediation="Run restore tests on a defined schedule and record results.",
        why_it_matters="Untested backups often fail during real incidents when recovery matters most.",
        framework_map="NIST PR.IP / CIS Control 11",
    ),
    Question(
        id="q12",
        text="Do you have a documented plan for responding to a cyber incident?",
        category="Incident Response",
        weight=9,
        impact=1.3,
        remediation="Create a concise incident response playbook with roles, contacts, and escalation steps.",
        why_it_matters="A defined response plan reduces confusion, downtime, and damage during incidents.",
        framework_map="NIST RS / CIS Control 17",
    ),
    Question(
        id="q13",
        text="Do employees receive regular cybersecurity awareness training?",
        category="Incident Response",
        weight=7,
        impact=1.1,
        remediation="Provide periodic training on phishing, passwords, safe browsing, and reporting.",
        why_it_matters="Human behavior is a major factor in phishing and credential compromise.",
        framework_map="NIST PR.AT / CIS Control 14",
    ),
    Question(
        id="q14",
        text="Do employees know how to report phishing or suspicious activity?",
        category="Incident Response",
        weight=7,
        impact=1.1,
        remediation="Set a simple reporting channel and teach staff when and how to use it.",
        why_it_matters="Fast reporting shortens attacker dwell time and improves containment.",
        framework_map="NIST RS.AN / CIS Control 17",
    ),
    Question(
        id="q15",
        text="Are admin accounts separate from normal user accounts?",
        category="Access Control",
        weight=8,
        impact=1.2,
        remediation="Use dedicated admin accounts for privileged activity and standard accounts for daily work.",
        why_it_matters="Separate admin accounts reduce the impact of phishing and routine misuse.",
        framework_map="NIST PR.AC / CIS Control 5, 6",
    ),
    Question(
        id="q16",
        text="Do you monitor for suspicious login attempts or unusual account activity?",
        category="Access Control",
        weight=7,
        impact=1.2,
        remediation="Enable alerting for anomalous logins, failed attempts, and impossible travel.",
        why_it_matters="Identity monitoring helps surface active account abuse early.",
        framework_map="NIST DE.CM / CIS Control 8",
    ),
    Question(
        id="q17",
        text="Are third-party tools or vendors reviewed before getting access to business data?",
        category="Data Protection",
        weight=5,
        impact=1.1,
        remediation="Establish a lightweight vendor review checklist before granting access.",
        why_it_matters="Third parties can introduce security and compliance risk into your environment.",
        framework_map="NIST ID.SC / CIS Control 15",
    ),
    Question(
        id="q18",
        text="Is there a clearly assigned owner for cybersecurity decisions?",
        category="Incident Response",
        weight=6,
        impact=1.1,
        remediation="Assign a named owner for security decisions, escalation, and accountability.",
        why_it_matters="Ownership is necessary to drive remediation and maintain security practices.",
        framework_map="NIST ID.GV / CIS Control 17",
    ),
]

ANSWER_FACTORS = {
    "Yes": 0.0,
    "Partially": 0.5,
    "No": 1.0,
    "Don't Know": 1.0,
}

URGENCY_FACTORS = {
    "Yes": 0.0,
    "Partially": 0.7,
    "No": 1.0,
    "Don't Know": 0.9,
}

CATEGORY_ORDER = [
    "Access Control",
    "Endpoint Security",
    "Data Protection",
    "Patch Management",
    "Backup & Recovery",
    "Incident Response",
]


# -----------------------------
# Scoring logic
# -----------------------------
def calculate_results(answers: Dict[str, str]) -> Dict:
    max_risk = sum(q.weight for q in QUESTIONS)
    total_risk = 0.0

    category_totals: Dict[str, Dict[str, float]] = {
        category: {"actual": 0.0, "max": 0.0} for category in CATEGORY_ORDER
    }

    findings = []

    for q in QUESTIONS:
        answer = answers.get(q.id, "Don't Know")
        factor = ANSWER_FACTORS[answer]
        urgency = URGENCY_FACTORS[answer]
        contribution = q.weight * factor
        total_risk += contribution

        category_totals[q.category]["actual"] += contribution
        category_totals[q.category]["max"] += q.weight

        if answer != "Yes":
            findings.append(
                {
                    "id": q.id,
                    "question": q.text,
                    "category": q.category,
                    "answer": answer,
                    "weight": q.weight,
                    "impact": q.impact,
                    "urgency": urgency,
                    "priority_score": round(q.weight * q.impact * urgency, 2),
                    "remediation": q.remediation,
                    "why_it_matters": q.why_it_matters,
                    "framework_map": q.framework_map,
                }
            )

    overall_score = round(100 * (1 - total_risk / max_risk)) if max_risk else 100

    if overall_score >= 80:
        risk_level = "Low"
    elif overall_score >= 60:
        risk_level = "Moderate"
    elif overall_score >= 40:
        risk_level = "High"
    else:
        risk_level = "Critical"

    category_scores = {}
    for category, vals in category_totals.items():
        score = round(100 * (1 - vals["actual"] / vals["max"])) if vals["max"] else 100
        category_scores[category] = score

    prioritized_findings = sorted(findings, key=lambda x: x["priority_score"], reverse=True)

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "category_scores": category_scores,
        "max_risk": max_risk,
        "actual_risk": round(total_risk, 2),
        "findings": prioritized_findings,
        "top_actions": prioritized_findings[:3],
    }


# -----------------------------
# Report generation
# -----------------------------
def build_llm_payload(org_name: str, org_type: str, org_size: str, results: Dict) -> Dict:
    return {
        "organization_name": org_name,
        "organization_type": org_type,
        "organization_size": org_size,
        "overall_score": results["overall_score"],
        "risk_level": results["risk_level"],
        "category_scores": results["category_scores"],
        "top_actions": [
            {
                "question": item["question"],
                "category": item["category"],
                "answer": item["answer"],
                "priority_score": item["priority_score"],
                "remediation": item["remediation"],
                "why_it_matters": item["why_it_matters"],
                "framework_map": item["framework_map"],
            }
            for item in results["top_actions"]
        ],
    }


def generate_demo_report(payload: Dict) -> str:
    actions = payload["top_actions"]
    weakest = sorted(payload["category_scores"].items(), key=lambda x: x[1])[:2]
    weakest_text = ", ".join([f"{k} ({v}/100)" for k, v in weakest])

    lines = []
    lines.append(f"Executive Summary\n{payload['organization_name']} is currently assessed at {payload['overall_score']}/100, which corresponds to a {payload['risk_level']} risk posture.")
    lines.append(f"The weakest control areas are {weakest_text}. The priority should be to reduce the highest-likelihood and highest-impact gaps first.")

    lines.append("Top 3 Priority Actions")
    for idx, item in enumerate(actions, start=1):
        lines.append(
            f"{idx}. {item['remediation']} This addresses the gap identified in {item['category']}. It matters because {item['why_it_matters']} Framework reference: {item['framework_map']}."
        )

    lines.append("30-Day Action Plan")
    for idx, item in enumerate(actions, start=1):
        lines.append(f"Week {idx}: {item['remediation']}")

    lines.append("Plain-English Takeaway")
    lines.append(
        "The fastest risk reduction will come from fixing identity, backup, and response readiness gaps before investing in lower-priority controls."
    )
    return "\n\n".join(lines)


def generate_ai_report(payload: Dict) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return generate_demo_report(payload)

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a cybersecurity advisor writing for non-technical organizations. "
        "Use plain language. Do not invent findings beyond the provided JSON. "
        "Return a concise report with these sections: Executive Summary, Top 3 Priority Actions, 30-Day Action Plan, Plain-English Takeaway."
    )

    user_prompt = f"Assessment JSON:\n{json.dumps(payload, indent=2)}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


# -----------------------------
# UI
# -----------------------------
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

# Persist answers across reruns
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

# Progress indicator
answered_count = sum(1 for q in QUESTIONS if q.id in answers)
total_count = len(QUESTIONS)
st.caption(f"{answered_count}/{total_count} answered")
if answered_count < total_count:
    st.info(f"{total_count - answered_count} question(s) not yet answered — they will be treated as \"Don't Know\".")

if st.button("Run Assessment", type="primary"):
    results = calculate_results(answers)
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

    # Downloadable CSV report
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
