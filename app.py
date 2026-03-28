import csv
import io

import xlsxwriter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from benchmarks import get_baseline, peer_comparison
from data import CATEGORY_ORDER, ORG_TYPE_WEIGHT_OVERRIDES, QUESTIONS
from history import get_all_assessments, get_last_assessment, save_assessment
from report import build_llm_payload, generate_ai_report
from scoring import calculate_results
from simulator import simulate_bundle, simulate_top_fixes

def _render_narrative_trend(all_entries: list) -> None:
    """Render a plain-language diff between the two most recent entries."""
    if len(all_entries) < 2:
        return
    prev = all_entries[-2]
    curr = all_entries[-1]
    lines = []

    prev_top = (prev.get("top_action_categories") or [None])[0]
    curr_top = (curr.get("top_action_categories") or [None])[0]
    if prev_top and curr_top:
        if prev_top == curr_top:
            lines.append(f"Top issue remains **{curr_top}** — unchanged since last run.")
        else:
            lines.append(f"Top issue shifted: **{prev_top}** → **{curr_top}**.")

    prev_threat = (prev.get("dominant_threats") or [None])[0]
    curr_threat = (curr.get("dominant_threats") or [None])[0]
    if prev_threat and curr_threat:
        if prev_threat != curr_threat:
            lines.append(f"Primary risk theme: **{prev_threat}** → **{curr_threat}**.")
        else:
            lines.append(f"Risk theme **{curr_threat}** persists.")

    prev_qw = prev.get("best_quick_win_label")
    curr_qw = curr.get("best_quick_win_label")
    if curr_qw:
        if prev_qw and prev_qw != curr_qw:
            lines.append(f"Best quick win moved from **{prev_qw}** to **{curr_qw}**.")
        elif prev_qw == curr_qw:
            lines.append(f"Best quick win is still **{curr_qw}** — consider prioritizing it.")

    if lines:
        st.markdown("**What changed:**")
        for line in lines:
            st.markdown(f"- {line}")


# ---------------------------------------------------------------------------
# Demo mode: pre-filled "small clinic with critical gaps" scenario
# ---------------------------------------------------------------------------
CLINIC_DEMO_ANSWERS = {
    "q1": "No",          # No MFA
    "q2": "Partially",   # Weak password hygiene
    "q3": "No",          # Former employees not removed promptly
    "q4": "Yes",         # Basic antivirus present
    "q5": "No",          # Devices not encrypted
    "q6": "Partially",   # Irregular patching
    "q7": "No",          # No patch tracking
    "q8": "Partially",   # Patient data partially secured
    "q9": "No",          # Broad data access
    "q10": "Yes",        # Backups exist
    "q11": "No",         # Backups never tested
    "q12": "No",         # No incident response plan
    "q13": "No",         # No security training
    "q14": "Partially",  # Some phishing awareness
    "q15": "No",         # No separate admin accounts
    "q16": "No",         # No login monitoring
    "q17": "Don't Know", # Vendor review unknown
    "q18": "No",         # No security owner
}

def _load_clinic_demo() -> None:
    st.session_state.answers = dict(CLINIC_DEMO_ANSWERS)
    for qid, ans in CLINIC_DEMO_ANSWERS.items():
        st.session_state[f"radio_{qid}"] = ans
    st.session_state["org_name"] = "Riverside Family Clinic"
    st.session_state["org_type"] = "Clinic"
    st.session_state["org_size"] = "11-50 employees"
    st.session_state["_trigger_run"] = True
    st.session_state["_demo_initialized"] = True


st.set_page_config(page_title="RiskLens AI", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    .hero-section {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b2a3b 60%, #1a3a4a 100%);
        border-radius: 12px;
        padding: 48px 48px 36px 48px;
        margin-bottom: 8px;
        color: #fff;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(99,210,255,0.15);
        border: 1px solid rgba(99,210,255,0.4);
        color: #63d2ff;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        padding: 4px 12px;
        border-radius: 20px;
        margin-bottom: 18px;
        text-transform: uppercase;
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        line-height: 1.2;
        margin: 0 0 12px 0;
        color: #fff;
    }
    .hero-title span { color: #63d2ff; }
    .hero-subtitle {
        font-size: 1.15rem;
        color: #b0c4d8;
        margin: 0 0 32px 0;
        max-width: 560px;
    }
    .hero-stats {
        display: flex;
        gap: 32px;
        margin-bottom: 36px;
        flex-wrap: wrap;
    }
    .hero-stat {
        text-align: center;
    }
    .hero-stat-number {
        font-size: 2rem;
        font-weight: 800;
        color: #63d2ff;
        line-height: 1;
    }
    .hero-stat-label {
        font-size: 0.82rem;
        color: #8aafc8;
        margin-top: 4px;
        white-space: nowrap;
    }
    .hero-cta {
        display: inline-block;
        background: #63d2ff;
        color: #0d1b2a !important;
        font-weight: 700;
        font-size: 1rem;
        padding: 12px 32px;
        border-radius: 8px;
        text-decoration: none !important;
        transition: background 0.2s;
        border: none;
        cursor: pointer;
    }
    .hero-cta:hover { background: #89dcff; }
    .hero-frameworks {
        margin-top: 28px;
        font-size: 0.8rem;
        color: #6a8fa8;
    }
    .hero-frameworks span {
        background: rgba(255,255,255,0.07);
        border-radius: 4px;
        padding: 2px 8px;
        margin-right: 6px;
    }
    </style>

    <div class="hero-section">
        <div class="hero-badge">🛡️ Cyber Risk Intelligence</div>
        <h1 class="hero-title">Cyber risk scores for small orgs<br>in <span>under 5 minutes</span></h1>
        <p class="hero-subtitle">
            Answer 18 plain-language questions. Get a scored risk report with prioritized fixes,
            peer benchmarks, and AI-generated remediation guidance — no security team required.
        </p>
        <div class="hero-stats">
            <div class="hero-stat">
                <div class="hero-stat-number">18</div>
                <div class="hero-stat-label">Security Controls</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-number">6</div>
                <div class="hero-stat-label">Risk Categories</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-number">&lt;5 min</div>
                <div class="hero-stat-label">To Complete</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-number">3</div>
                <div class="hero-stat-label">Frameworks Mapped</div>
            </div>
        </div>
        <a class="hero-cta" href="#assessment-questionnaire">Start Assessment ↓</a>
        <div class="hero-frameworks">
            Framework coverage: &nbsp;
            <span>NIST CSF</span><span>CIS Controls</span><span>ISO 27001</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    # --- Demo mode: URL param or button ---
    if st.query_params.get("demo") == "clinic" and not st.session_state.get("_demo_initialized"):
        _load_clinic_demo()

    st.markdown("### Try a Demo")
    if st.button("🏥 Load Clinic Demo", help="Pre-fills a small clinic with critical security gaps — skip straight to results", use_container_width=True):
        _load_clinic_demo()
        st.rerun()
    st.caption("Skips the questionnaire and shows a realistic high-risk clinic scenario.")
    st.markdown("---")

    st.header("Organization Profile")
    if "org_name" not in st.session_state:
        st.session_state["org_name"] = "Sample Organization"
    org_name = st.text_input("Organization Name", key="org_name")
    _org_type_options = ["Small Business", "Nonprofit", "School", "Clinic", "Startup", "Other"]
    if "org_type" not in st.session_state:
        st.session_state["org_type"] = "Small Business"
    org_type = st.selectbox("Organization Type", _org_type_options, key="org_type")
    _org_size_options = ["1-10 employees", "11-50 employees", "51-200 employees", "201+ employees"]
    if "org_size" not in st.session_state:
        st.session_state["org_size"] = "1-10 employees"
    org_size = st.selectbox("Organization Size", _org_size_options, key="org_size")
    st.markdown("---")
    st.write("Scoring bands")
    st.write("80–100: Low")
    st.write("60–79: Moderate")
    st.write("40–59: High")
    st.write("0–39: Critical")

st.markdown('<div id="assessment-questionnaire"></div>', unsafe_allow_html=True)
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
            # Adaptive follow-up prompts for weak/unknown answers
            if selection in ("No", "Don't Know") and q.follow_up_if_no:
                for prompt in q.follow_up_if_no:
                    st.info(f"**Context:** {prompt}", icon="💡")

answers = st.session_state.answers

answered_count = sum(1 for q in QUESTIONS if q.id in answers)
total_count = len(QUESTIONS)
st.caption(f"{answered_count}/{total_count} answered")
if answered_count < total_count:
    st.info(f"{total_count - answered_count} question(s) not yet answered — they will be treated as \"Don't Know\".")

if st.button("Run Assessment", type="primary") or st.session_state.pop("_trigger_run", False):
    prior = get_last_assessment(org_name)
    results = calculate_results(answers, org_type=org_type)
    save_assessment(org_name, org_type, org_size, results)
    payload = build_llm_payload(org_name, org_type, org_size, results)
    report = generate_ai_report(payload)
    top_sims = simulate_top_fixes(answers, org_type=org_type, limit=5)

    st.session_state["_results"] = results
    st.session_state["_prior"] = prior
    st.session_state["_payload"] = payload
    st.session_state["_report"] = report
    st.session_state["_top_sims"] = top_sims
    st.session_state["_answers_snap"] = dict(answers)
    st.session_state["_org_type_snap"] = org_type
    st.session_state["_org_name_snap"] = org_name
    st.session_state["_org_size_snap"] = org_size

if "_results" not in st.session_state:
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
        _render_narrative_trend(all_entries)
else:
    results = st.session_state["_results"]
    prior = st.session_state["_prior"]
    payload = st.session_state["_payload"]
    report = st.session_state["_report"]
    top_sims = st.session_state["_top_sims"]
    answers_snap = st.session_state["_answers_snap"]
    org_type_snap = st.session_state["_org_type_snap"]
    org_name_snap = st.session_state["_org_name_snap"]
    org_size_snap = st.session_state["_org_size_snap"]

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

    # --- How is my score calculated? ---
    with st.expander("🔍 How is my score calculated?"):
        st.markdown(
            """
**RiskLens AI uses a fully deterministic, transparent formula — no black-box AI, no hidden model.**

---
### Step 1 — Answer factors
Each answer maps to a **risk factor** (how much risk the answer contributes):

| Answer | Risk factor |
|---|---|
| Yes | 0.0 (no risk) |
| Partially | 0.5 |
| No | 1.0 (full risk) |
| Don't Know | 1.0 (treated as No) |

---
### Step 2 — Question weights
Each control has a **weight** (1–12) reflecting its relative importance. Higher weight = bigger impact on your score.
"""
        )

        overrides = ORG_TYPE_WEIGHT_OVERRIDES.get(org_type_snap, {})
        weight_rows = []
        for q in QUESTIONS:
            base_w = q.weight
            override_w = overrides.get(q.id)
            if override_w is not None:
                w_display = f"{override_w} (base: {base_w}, boosted for {org_type_snap})"
            else:
                w_display = str(base_w)
            weight_rows.append({
                "#": q.id.upper(),
                "Control": q.text,
                "Category": q.category,
                "Weight": w_display,
            })
        st.dataframe(weight_rows, use_container_width=True, hide_index=True)

        st.markdown(
            f"""
---
### Step 3 — Overall score formula

```
risk_contribution  = weight × answer_factor        (per question)
total_risk         = Σ risk_contributions           (all 18 questions)
max_possible_risk  = Σ weights                      (if every answer were "No")
overall_score      = 100 × (1 − total_risk / max_possible_risk)
```

**Your numbers this run:**
- Max possible risk: **{results['max_risk']}**
- Actual risk accumulated: **{results['actual_risk']}**
- Overall score: **100 × (1 − {results['actual_risk']} / {results['max_risk']}) = {results['overall_score']}/100**

---
### Step 4 — Category scores
The same formula applies within each category using only the questions that belong to it.

---
### Step 5 — Priority ranking (ROI score)
Failing controls are ranked by:
```
risk_score = weight × impact × urgency_factor
roi_score  = (risk_score × time_to_value_factor) / effort_factor
```

**Urgency factors** — how seriously each answer counts toward prioritization:

| Answer | Urgency factor |
|---|---|
| No | 1.0 |
| Don't Know | 0.9 |
| Partially | 0.7 |

**Effort factors:** Low = 1 · Medium = 2 · High = 3

**Time-to-value factors:** Days = 1.2 · Weeks = 1.0 · Months = 0.8

Higher ROI score → control appears earlier in your priority action list.

---
### Risk bands
| Score | Risk level |
|---|---|
| 80–100 | Low |
| 60–79 | Moderate |
| 40–59 | High |
| 0–39 | Critical |
"""
        )

    # --- Section A: Biggest Risk Right Now ---
    pls = results["plain_language_summary_data"]
    weakest_cats = pls["weakest_categories"]
    dominant = results["dominant_threats"]

    if weakest_cats:
        weakest_cat = weakest_cats[0]["category"]
        weakest_score = weakest_cats[0]["score"]
        threat_str = " and ".join(dominant[:2]) if dominant else "multiple attack vectors"
        business_exp = (
            f"Biggest current exposure: **{weakest_cat}** (score: {weakest_score}/100) "
            f"driven by {threat_str}."
        )
        st.markdown("---")
        with st.container(border=True):
            st.markdown("### Biggest Risk Right Now")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Highest-Risk Category", weakest_cat, f"{weakest_score}/100", delta_color="inverse")
                st.metric("Top Threat Theme", dominant[0] if dominant else "—")
            with col_b:
                st.markdown("**Business exposure:**")
                st.markdown(business_exp)
                if len(weakest_cats) > 1:
                    st.caption(
                        "Also exposed: "
                        + ", ".join(f"{w['category']} ({w['score']}/100)" for w in weakest_cats[1:])
                    )

    all_entries = get_all_assessments(org_name)

    if prior:
        st.subheader("Change vs Last Assessment")
        st.caption(f"Compared to {prior['date']}")
        cols = st.columns(len(results["category_scores"]))
        for col, (cat, score) in zip(cols, results["category_scores"].items()):
            prev_score = prior["category_scores"].get(cat)
            col.metric(cat, f"{score}/100", delta=score - prev_score if prev_score is not None else None)

    if len(all_entries) >= 2:
        st.markdown("---")
        st.subheader("Score Trend")
        st.caption(f"{len(all_entries)} runs recorded for {org_name}")
        df = pd.DataFrame(
            [{"Overall": e["overall_score"], **e["category_scores"]} for e in all_entries],
            index=range(1, len(all_entries) + 1),
        )
        df.index.name = "Run"
        st.line_chart(df)
        _render_narrative_trend(all_entries)

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

    # --- Peer Benchmark Comparison ---
    baseline = get_baseline(org_type_snap)
    comparisons = peer_comparison(org_type_snap, results["category_scores"])
    overall_delta = results["overall_score"] - baseline["overall"]

    st.markdown("---")
    with st.container(border=True):
        st.markdown("### Compared to Peers")
        st.caption(
            f"Prototype benchmark baselines derived from expert heuristics and assessment design assumptions "
            f"for **{org_type_snap}** organizations."
        )
        ov_col, _ = st.columns([1, 2])
        ov_col.metric(
            "Overall vs Sector Baseline",
            f"{results['overall_score']}/100",
            delta=overall_delta,
            delta_color="normal",
            help=f"Sector baseline: {baseline['overall']}/100",
        )

        # Grouped bar chart: org vs baseline per category
        bench_cats = [c["category"] for c in comparisons]
        bench_org = [c["org_score"] for c in comparisons]
        bench_base = [c["baseline_score"] for c in comparisons]
        bench_colors = []
        for c in comparisons:
            if c["status"] == "above":
                bench_colors.append("#2ca02c")
            elif c["status"] == "below":
                bench_colors.append("#d62728")
            else:
                bench_colors.append("#1f77b4")
        bench_fig = go.Figure(data=[
            go.Bar(name="Your Score", x=bench_cats, y=bench_org, marker_color=bench_colors),
            go.Bar(name="Sector Baseline", x=bench_cats, y=bench_base, marker_color="rgba(150,150,150,0.5)"),
        ])
        bench_fig.update_layout(
            barmode="group",
            yaxis=dict(range=[0, 100], title="Score"),
            height=280,
            margin=dict(t=10, b=10, l=40, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(bench_fig, use_container_width=True)

        # Comparison table
        STATUS_ICON = {"above": "✅ Above", "on-par": "➖ On par", "below": "🔴 Below"}
        tbl_rows = ""
        for c in comparisons:
            delta_str = f"+{c['delta']}" if c['delta'] > 0 else str(c['delta'])
            status_str = STATUS_ICON.get(c["status"], c["status"])
            tbl_rows += (
                f"<tr>"
                f"<td style='padding:5px 10px'>{c['category']}</td>"
                f"<td style='padding:5px 10px;text-align:center'><b>{c['org_score']}</b></td>"
                f"<td style='padding:5px 10px;text-align:center'>{c['baseline_score']}</td>"
                f"<td style='padding:5px 10px;text-align:center'>{delta_str}</td>"
                f"<td style='padding:5px 10px;text-align:center'>{status_str}</td>"
                f"</tr>"
            )
        # Overall row
        ov_delta_str = f"+{overall_delta}" if overall_delta > 0 else str(overall_delta)
        tbl_rows += (
            f"<tr style='font-weight:bold;border-top:2px solid #ccc'>"
            f"<td style='padding:5px 10px'>Overall</td>"
            f"<td style='padding:5px 10px;text-align:center'>{results['overall_score']}</td>"
            f"<td style='padding:5px 10px;text-align:center'>{baseline['overall']}</td>"
            f"<td style='padding:5px 10px;text-align:center'>{ov_delta_str}</td>"
            f"<td style='padding:5px 10px;text-align:center'>"
            f"{'✅ Above' if overall_delta > 3 else ('🔴 Below' if overall_delta < -3 else '➖ On par')}"
            f"</td>"
            f"</tr>"
        )
        st.markdown(
            "<table style='width:100%;border-collapse:collapse;font-size:0.88rem'>"
            "<thead><tr style='background:#f0f0f0'>"
            "<th style='padding:5px 10px;text-align:left'>Category</th>"
            "<th style='padding:5px 10px'>You</th>"
            "<th style='padding:5px 10px'>Sector avg</th>"
            "<th style='padding:5px 10px'>Delta</th>"
            "<th style='padding:5px 10px'>Status</th>"
            f"</tr></thead><tbody>{tbl_rows}</tbody></table>",
            unsafe_allow_html=True,
        )

        common_weak = baseline["common_weak_spots"]
        st.caption(
            f"Common weak spots for {org_type_snap}s: "
            + ", ".join(f"**{w}**" for w in common_weak)
            + ". Baselines are design-derived heuristics, not external survey data."
        )

    st.subheader("Controls Traffic Light")

    def _traffic_color(answer: str) -> str:
        return {"Yes": "#d4edda", "Partially": "#fff3cd"}.get(answer, "#f8d7da")

    def _traffic_label(answer: str) -> str:
        return {"Yes": "✅ Yes", "Partially": "⚠️ Partially"}.get(answer, "🔴 " + answer)

    rows_html = ""
    for q in QUESTIONS:
        answer = answers_snap.get(q.id, "Don't Know")
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
    for i, action in enumerate(results["top_actions"][:3], start=1):
        with st.container(border=True):
            st.markdown(f"**{i}. {action['category']}**")
            st.write(action["question"])
            st.write(f"Answer: {action['answer']}")
            st.write(f"Priority Score: {action['roi_score']}")
            st.write(f"Recommended Fix: {action['remediation']}")
            st.write(f"Why it matters: {action['why_it_matters']}")
            st.write(f"Framework mapping: {action['framework_map']}")

    # --- Section B: Best Next Fix (top simulation result) ---
    if top_sims:
        best = top_sims[0]
        st.markdown("---")
        with st.container(border=True):
            st.markdown("### Best Next Fix")
            st.caption(f"{best.get('category', '')} · {'⚡ Quick Win' if best.get('quick_win') else 'Strategic Fix'}")
            st.markdown(f"**{best['question']}**")
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Score Gain", f"+{best['score_delta']} pts")
            b2.metric("Effort", best.get("effort", "—"))
            b3.metric("Time to Value", best.get("time_to_value", "—"))
            b4.metric("Risk Level After", best["risk_level_after"])
            if best.get("threats_reduced"):
                st.markdown(
                    "Threats mitigated: " + ", ".join(f"`{t}`" for t in best["threats_reduced"])
                )
            if best.get("remediation"):
                st.info(f"**How to fix:** {best['remediation']}")

    # --- Ranked simulation results ---
    if len(top_sims) > 1:
        with st.expander(f"See all top {len(top_sims)} single-fix simulations"):
            for i, sim in enumerate(top_sims, 1):
                cols = st.columns([4, 1, 1, 1])
                label = f"**{i}. {sim['question']}**"
                if sim.get("quick_win"):
                    label += " ⚡"
                cols[0].markdown(label)
                cols[0].caption(sim.get("category", ""))
                cols[1].metric("Score +", f"{sim['score_delta']} pts")
                cols[2].metric("Effort", sim.get("effort", "—"))
                cols[3].metric("Time", sim.get("time_to_value", "—"))

    # --- Section C: What If Simulator ---
    # Use all failing controls as options so every unmet control is selectable,
    # not just the subset with a positive simulation_gain_hint.
    sim_pool = results["findings_by_roi"]
    if sim_pool:
        st.markdown("---")
        st.subheader("What If Simulator")
        st.caption("Pick controls to fix and see the projected impact on your score and risk level.")

        sim_options = {f["question"]: f["id"] for f in sim_pool}
        sim_labels = list(sim_options.keys())

        col_sel, col_multi = st.columns(2)
        with col_sel:
            single_label = st.selectbox(
                "Simulate fixing a single control:",
                options=sim_labels,
                key="sim_single",
            )
        with col_multi:
            bundle_labels = st.multiselect(
                "Or bundle multiple fixes together:",
                options=sim_labels,
                key="sim_bundle",
            )

        if bundle_labels:
            selected_ids = [sim_options[lbl] for lbl in bundle_labels]
        elif single_label is not None and single_label in sim_options:
            selected_ids = [sim_options[single_label]]
        else:
            selected_ids = []

        def _risk_color(level: str) -> str:
            return {"Low": "green", "Moderate": "orange", "High": "red", "Critical": "red"}.get(level, "gray")

        if selected_ids:
            sim_result = simulate_bundle(answers_snap, selected_ids, org_type=org_type_snap)

            sim_c1, sim_c2 = st.columns(2)
            with sim_c1:
                st.markdown("#### Current")
                st.metric("Score", f"{sim_result['score_before']}/100")
                level_b = sim_result["risk_level_before"]
                st.markdown(f"Risk Level: :{_risk_color(level_b)}[**{level_b}**]")
            with sim_c2:
                st.markdown("#### After Simulated Fix")
                st.metric("Score", f"{sim_result['score_after']}/100", delta=sim_result["score_delta"])
                level_a = sim_result["risk_level_after"]
                st.markdown(f"Risk Level: :{_risk_color(level_a)}[**{level_a}**]")
                if sim_result["risk_level_changed"]:
                    st.success(f"Risk level would drop: **{level_b}** → **{level_a}**")

            if sim_result["category_deltas"]:
                st.markdown("**Category improvements:**")
                delta_cols = st.columns(len(sim_result["category_deltas"]))
                for col, (cat, delta) in zip(delta_cols, sim_result["category_deltas"].items()):
                    col.metric(cat, f"+{delta} pts")

            if sim_result["threats_reduced"]:
                st.markdown(
                    "**Threats reduced:** " + ", ".join(f"`{t}`" for t in sim_result["threats_reduced"])
                )

            # Show remediation steps for each selected control
            selected_sims = [s for s in top_sims if s["question_id"] in selected_ids]
            # Also pull from sim_pool for controls not in top_sims
            sim_pool_by_id = {f["id"]: f for f in sim_pool}
            st.markdown("**Remediation steps:**")
            for qid in selected_ids:
                match = next((s for s in top_sims if s["question_id"] == qid), None)
                label = match["question"] if match else sim_pool_by_id.get(qid, {}).get("question", qid)
                fix = match.get("remediation") if match else sim_pool_by_id.get(qid, {}).get("remediation")
                if fix:
                    st.markdown(f"- **{label}**: {fix}")

    # --- Section D: Quick Wins vs Strategic Fixes ---
    quick_wins = results["quick_wins"]
    strategic = [f for f in results["findings_by_risk"] if not f["quick_win"]]

    st.markdown("---")
    st.subheader("Quick Wins vs Strategic Fixes")
    d_left, d_right = st.columns(2)

    with d_left:
        st.markdown("#### Quick Wins")
        st.caption("Low effort · Fast value")
        if quick_wins:
            for f in quick_wins[:5]:
                with st.container(border=True):
                    st.markdown(f"**{f['category']}** — `{f['urgency']}` urgency")
                    st.write(f["question"])
                    st.caption(f"Effort: {f['effort']} · Time to Value: {f['time_to_value']}")
                    if f.get("follow_up_if_no"):
                        st.info(f["follow_up_if_no"])
                    if f.get("business_impact"):
                        st.caption(f"Business impact: {f['business_impact']}")
        else:
            st.info("No quick wins identified — focus on strategic fixes first.")

    with d_right:
        st.markdown("#### Strategic Fixes")
        st.caption("High impact · Longer-term investment")
        if strategic:
            for f in strategic[:5]:
                with st.container(border=True):
                    st.markdown(f"**{f['category']}** — `{f['urgency']}` urgency")
                    st.write(f["question"])
                    st.caption(f"Risk Score: {f['risk_score']} · Effort: {f['effort']}")
                    if f.get("follow_up_if_no"):
                        st.info(f["follow_up_if_no"])
                    if f.get("business_impact"):
                        st.caption(f"Business impact: {f['business_impact']}")
        else:
            st.info("No high-risk strategic gaps identified.")

    st.subheader("AI Recommendation Agent")
    st.markdown(report)

    with st.expander("Structured JSON Output"):
        st.json(payload)

    # --- Excel report with charts ---
    xl_buf = io.BytesIO()
    workbook = xlsxwriter.Workbook(xl_buf, {"in_memory": True})

    # Formats
    fmt_title = workbook.add_format({"bold": True, "font_size": 14})
    fmt_header = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
    fmt_bold = workbook.add_format({"bold": True})
    fmt_border = workbook.add_format({"border": 1})

    # Sheet 1: Summary
    ws_sum = workbook.add_worksheet("Summary")
    ws_sum.set_column("A:A", 30)
    ws_sum.set_column("B:B", 20)
    ws_sum.write("A1", "RiskLens AI — Assessment Report", fmt_title)
    ws_sum.write("A2", "Organization", fmt_bold)
    ws_sum.write("B2", org_name_snap)
    ws_sum.write("A3", "Type", fmt_bold)
    ws_sum.write("B3", org_type_snap)
    ws_sum.write("A4", "Size", fmt_bold)
    ws_sum.write("B4", org_size_snap)
    ws_sum.write("A5", "Overall Score", fmt_bold)
    ws_sum.write("B5", results["overall_score"])
    ws_sum.write("A6", "Risk Level", fmt_bold)
    ws_sum.write("B6", results["risk_level"])

    ws_sum.write("A8", "Category Scores", fmt_title)
    ws_sum.write("A9", "Category", fmt_header)
    ws_sum.write("B9", "Score", fmt_header)
    for row_i, (cat, score) in enumerate(results["category_scores"].items(), start=9):
        ws_sum.write(row_i, 0, cat, fmt_border)
        ws_sum.write(row_i, 1, score, fmt_border)

    # Radar chart for category scores
    radar = workbook.add_chart({"type": "radar", "subtype": "filled"})
    n_cats = len(results["category_scores"])
    radar.add_series({
        "name": "Score",
        "categories": ["Summary", 9, 0, 9 + n_cats - 1, 0],
        "values":     ["Summary", 9, 1, 9 + n_cats - 1, 1],
        "fill": {"color": "#4472C4", "transparency": 50},
        "line": {"color": "#4472C4"},
    })
    radar.set_title({"name": "Category Scores"})
    radar.set_y_axis({"min": 0, "max": 100})
    radar.set_size({"width": 420, "height": 320})
    ws_sum.insert_chart("D8", radar)

    # Sheet 2: Peer Benchmark
    ws_bench = workbook.add_worksheet("Peer Benchmark")
    ws_bench.set_column("A:A", 30)
    ws_bench.set_column("B:D", 16)
    ws_bench.write("A1", "Peer Benchmark Comparison", fmt_title)
    ws_bench.write("A2", f"Sector: {org_type_snap}", fmt_bold)
    ws_bench.write("A4", "Category", fmt_header)
    ws_bench.write("B4", "Your Score", fmt_header)
    ws_bench.write("C4", "Sector Baseline", fmt_header)
    ws_bench.write("D4", "Delta", fmt_header)
    for row_i, c in enumerate(comparisons, start=4):
        ws_bench.write(row_i, 0, c["category"], fmt_border)
        ws_bench.write(row_i, 1, c["org_score"], fmt_border)
        ws_bench.write(row_i, 2, c["baseline_score"], fmt_border)
        ws_bench.write(row_i, 3, c["delta"], fmt_border)
    # Overall row
    ov_row = 4 + len(comparisons)
    ws_bench.write(ov_row, 0, "Overall", fmt_bold)
    ws_bench.write(ov_row, 1, results["overall_score"], fmt_bold)
    ws_bench.write(ov_row, 2, baseline["overall"], fmt_bold)
    ws_bench.write(ov_row, 3, overall_delta, fmt_bold)

    # Grouped bar chart: org vs baseline
    bar = workbook.add_chart({"type": "bar"})
    n_bench = len(comparisons)
    bar.add_series({
        "name": "Your Score",
        "categories": ["Peer Benchmark", 4, 0, 4 + n_bench - 1, 0],
        "values":     ["Peer Benchmark", 4, 1, 4 + n_bench - 1, 1],
        "fill": {"color": "#4472C4"},
    })
    bar.add_series({
        "name": "Sector Baseline",
        "categories": ["Peer Benchmark", 4, 0, 4 + n_bench - 1, 0],
        "values":     ["Peer Benchmark", 4, 2, 4 + n_bench - 1, 2],
        "fill": {"color": "#A9A9A9"},
    })
    bar.set_title({"name": "Your Score vs Sector Baseline"})
    bar.set_x_axis({"min": 0, "max": 100, "name": "Score"})
    bar.set_size({"width": 480, "height": 320})
    ws_bench.insert_chart("F4", bar)

    # Sheet 3: Findings
    ws_find = workbook.add_worksheet("Findings")
    ws_find.set_column("A:A", 6)
    ws_find.set_column("B:B", 22)
    ws_find.set_column("C:C", 40)
    ws_find.set_column("D:D", 14)
    ws_find.set_column("E:H", 20)
    headers = ["#", "Category", "Question", "Answer", "Priority Score", "Remediation", "Why It Matters", "Framework Map"]
    for col_i, h in enumerate(headers):
        ws_find.write(0, col_i, h, fmt_header)
    for row_i, f in enumerate(results["findings"], start=1):
        ws_find.write(row_i, 0, row_i, fmt_border)
        ws_find.write(row_i, 1, f["category"], fmt_border)
        ws_find.write(row_i, 2, f["question"], fmt_border)
        ws_find.write(row_i, 3, f["answer"], fmt_border)
        ws_find.write(row_i, 4, f["roi_score"], fmt_border)
        ws_find.write(row_i, 5, f["remediation"], fmt_border)
        ws_find.write(row_i, 6, f["why_it_matters"], fmt_border)
        ws_find.write(row_i, 7, f["framework_map"], fmt_border)

    # Sheet 4: AI Report
    ws_ai = workbook.add_worksheet("AI Report")
    ws_ai.set_column("A:A", 100)
    ws_ai.write("A1", "AI Recommendation Agent", fmt_title)
    ws_ai.write("A3", report)

    workbook.close()
    xl_buf.seek(0)

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["RiskLens AI — Assessment Report"])
    writer.writerow(["Organization", org_name_snap, "Type", org_type_snap, "Size", org_size_snap])
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
        writer.writerow([i, f["category"], f["question"], f["answer"], f["roi_score"], f["remediation"], f["why_it_matters"], f["framework_map"]])
    writer.writerow([])
    writer.writerow(["AI Recommendation Agent"])
    writer.writerow([report])

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            label="Download Report as CSV",
            data=csv_buf.getvalue(),
            file_name=f"risklens_report_{org_name_snap.replace(' ', '_')}.csv",
            mime="text/csv",
        )
    with dl_col2:
        st.download_button(
            label="Download Report as Excel (with charts)",
            data=xl_buf.getvalue(),
            file_name=f"risklens_report_{org_name_snap.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

