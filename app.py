import csv
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from benchmarks import get_baseline, peer_comparison
from data import CATEGORY_ORDER, QUESTIONS
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

if st.button("Run Assessment", type="primary"):
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

    st.subheader("AI Report")
    st.text_area("Generated Assessment Report", value=report, height=380)

    with st.expander("Structured JSON Output"):
        st.json(payload)

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
    writer.writerow(["AI Report"])
    writer.writerow([report])

    st.download_button(
        label="Download Report as CSV",
        data=csv_buf.getvalue(),
        file_name=f"risklens_report_{org_name_snap.replace(' ', '_')}.csv",
        mime="text/csv",
    )

