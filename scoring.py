from typing import Dict

from data import (
    ANSWER_FACTORS,
    CATEGORY_ORDER,
    ORG_TYPE_WEIGHT_OVERRIDES,
    QUESTIONS,
    URGENCY_FACTORS,
    Question,
)


def calculate_results(answers: Dict[str, str], org_type: str = "") -> Dict:
    overrides = ORG_TYPE_WEIGHT_OVERRIDES.get(org_type, {})

    def effective_weight(q: Question) -> int:
        return overrides.get(q.id, q.weight)

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
            findings.append(
                {
                    "id": q.id,
                    "question": q.text,
                    "category": q.category,
                    "answer": answer,
                    "weight": w,
                    "impact": q.impact,
                    "urgency": urgency,
                    "priority_score": round(w * q.impact * urgency, 2),
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
