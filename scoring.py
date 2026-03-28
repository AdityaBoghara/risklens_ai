from collections import Counter
from typing import Dict, List

from data import (
    ANSWER_FACTORS,
    CATEGORY_ORDER,
    ORG_TYPE_WEIGHT_OVERRIDES,
    QUESTIONS,
    URGENCY_FACTORS,
    Question,
)

EFFORT_SCORES: Dict[str, int] = {"Low": 1, "Medium": 2, "High": 3}
TIME_TO_VALUE_SCORES: Dict[str, float] = {"Days": 1.2, "Weeks": 1.0, "Months": 0.8}


def calculate_results(answers: Dict[str, str], org_type: str = "") -> Dict:
    overrides = ORG_TYPE_WEIGHT_OVERRIDES.get(org_type, {})

    def effective_weight(q: Question) -> int:
        base = overrides.get(q.id, q.weight)
        # Apply per-org relevance boost from the question itself
        if q.org_relevance and org_type in q.org_relevance:
            base += q.org_relevance[org_type]
        return base

    max_risk = sum(effective_weight(q) for q in QUESTIONS)
    total_risk = 0.0

    category_totals: Dict[str, Dict[str, float]] = {
        category: {"actual": 0.0, "max": 0.0} for category in CATEGORY_ORDER
    }

    findings = []

    for q in QUESTIONS:
        w = effective_weight(q)
        answer = answers.get(q.id, "Don't Know")
        factor = ANSWER_FACTORS[answer]
        urgency = URGENCY_FACTORS[answer]
        contribution = w * factor
        total_risk += contribution

        category_totals[q.category]["actual"] += contribution
        category_totals[q.category]["max"] += w

        if answer != "Yes":
            risk_score = round(w * q.impact * urgency, 2)
            effort = EFFORT_SCORES[q.effort]
            ttv = TIME_TO_VALUE_SCORES[q.time_to_value]
            roi_score = round((risk_score * ttv) / effort, 3)

            findings.append(
                {
                    "id": q.id,
                    "question": q.text,
                    "category": q.category,
                    "answer": answer,
                    "urgency": urgency,
                    "risk_score": risk_score,
                    "roi_score": roi_score,
                    "effort": q.effort,
                    "time_to_value": q.time_to_value,
                    "quick_win": q.qwuick_win,
                    "threats": q.threats,
                    "business_impact": q.business_impact,
                    "simulation_gain_hint": q.simulation_gain_hint,
                    "depends_on": q.depends_on,
                    "follow_up_if_no": q.follow_up_if_no,
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

    # IDs of all failing controls
    failing_ids = {f["id"] for f in findings}

    # A control is blocked if any prerequisite is itself failing
    def is_blocked(finding: Dict) -> bool:
        return any(dep in failing_ids for dep in finding["depends_on"])

    control_dependencies_blocked: List[Dict] = [
        {"id": f["id"], "question": f["question"], "blocked_by": [d for d in f["depends_on"] if d in failing_ids]}
        for f in findings
        if is_blocked(f)
    ]
    blocked_ids = {b["id"] for b in control_dependencies_blocked}

    findings_by_risk = sorted(findings, key=lambda x: x["risk_score"], reverse=True)
    findings_by_roi = sorted(findings, key=lambda x: x["roi_score"], reverse=True)

    # Quick wins: marked as such in question data and not blocked by unresolved deps
    quick_wins = [f for f in findings_by_roi if f["quick_win"] and f["id"] not in blocked_ids]

    # Top actions: ROI-ranked, unblocked controls first, then blocked ones appended at end
    unblocked_by_roi = [f for f in findings_by_roi if f["id"] not in blocked_ids]
    blocked_by_roi = [f for f in findings_by_roi if f["id"] in blocked_ids]
    top_actions = (unblocked_by_roi + blocked_by_roi)[:5]

    # Simulations: every failing control with a non-zero gain hint, sorted by hint desc
    simulations = sorted(
        [
            {
                "id": f["id"],
                "question": f["question"],
                "category": f["category"],
                "answer": f["answer"],
                "risk_score": f["risk_score"],
                "simulation_gain_hint": f["simulation_gain_hint"],
            }
            for f in findings
            if f["simulation_gain_hint"] > 0
        ],
        key=lambda x: x["simulation_gain_hint"],
        reverse=True,
    )

    # Threat aggregation across all failing controls
    threat_counter: Counter = Counter()
    for f in findings:
        threat_counter.update(f["threats"])
    threat_summary = dict(threat_counter.most_common())
    dominant_threats: List[str] = [t for t, _ in threat_counter.most_common(3)]

    # Plain-language summary data: weakest categories + dominant threats
    weakest_categories = sorted(
        [(cat, score) for cat, score in category_scores.items()],
        key=lambda x: x[1],
    )[:3]
    plain_language_summary_data = {
        "weakest_categories": [{"category": cat, "score": score} for cat, score in weakest_categories],
        "dominant_threats": dominant_threats,
        "total_failing": len(findings),
        "quick_win_count": len(quick_wins),
    }

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "category_scores": category_scores,
        "max_risk": max_risk,
        "actual_risk": round(total_risk, 2),
        "findings_by_risk": findings_by_risk,
        "findings_by_roi": findings_by_roi,
        "quick_wins": quick_wins,
        "simulations": simulations,
        "threat_summary": threat_summary,
        "dominant_threats": dominant_threats,
        "control_dependencies_blocked": control_dependencies_blocked,
        "top_actions": top_actions,
        "plain_language_summary_data": plain_language_summary_data,
        # Keep legacy key so existing callers don't break before they're updated
        "findings": findings_by_risk,
    }
