import json
import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_ORG_TYPE_NOTES = {
    "Healthcare": (
        "Healthcare organizations face elevated HIPAA obligations and ransomware targeting of patient data. "
        "PHI loss triggers mandatory breach notification, regulatory fines, and reputational harm. "
        "Prioritize identity controls and backup integrity above all else."
    ),
    "Finance": (
        "Financial organizations are high-value targets for credential theft, wire fraud, and supply-chain attacks. "
        "PCI-DSS, SOX, and state data laws create layered compliance exposure. "
        "Access controls and transaction monitoring carry outsized weight here."
    ),
    "Education": (
        "Educational institutions hold student PII and research IP with limited IT budgets. "
        "FERPA obligations and frequent phishing of students/staff create broad attack surface. "
        "Endpoint hygiene and email security are common weak points."
    ),
    "Nonprofit": (
        "Nonprofits often rely on volunteers and shared credentials, increasing insider-risk exposure. "
        "Donor PII and grant data are high-value targets. "
        "Low-cost controls like MFA and password managers deliver outsized ROI."
    ),
    "Government": (
        "Government entities face nation-state and ransomware threats with high public-accountability stakes. "
        "FISMA/NIST frameworks apply and audit trails are critical. "
        "Patch cadence and privileged-access management are common gaps."
    ),
    "Retail": (
        "Retail organizations process payment card data and face PCI-DSS scope across POS and e-commerce channels. "
        "Supply-chain compromise through third-party integrations is a leading vector. "
        "Segment cardholder environments and monitor third-party access closely."
    ),
    "Technology": (
        "Technology firms are high-profile targets for IP theft and supply-chain poisoning. "
        "Developer toolchains and CI/CD pipelines are attack surfaces often overlooked in risk assessments. "
        "Code signing, secret management, and repo access controls are critical."
    ),
}


def _slim_finding(item: Dict) -> Dict:
    """Return a reduced view of a finding for LLM context (omit heavy/redundant fields)."""
    return {
        "id": item["id"],
        "question": item["question"],
        "category": item["category"],
        "answer": item["answer"],
        "roi_score": item["roi_score"],
        "risk_score": item["risk_score"],
        "effort": item["effort"],
        "time_to_value": item["time_to_value"],
        "remediation": item["remediation"],
        "why_it_matters": item["why_it_matters"],
        "threats": item["threats"],
        "simulation_gain_hint": item["simulation_gain_hint"],
        "framework_map": item["framework_map"],
    }


def build_llm_payload(org_name: str, org_type: str, org_size: str, results: Dict) -> Dict:
    findings_by_roi = results.get("findings_by_roi", [])
    quick_wins = results.get("quick_wins", [])
    simulations = results.get("simulations", [])
    blocked = results.get("control_dependencies_blocked", [])
    category_scores = results["category_scores"]

    blocked_ids = {b["id"] for b in blocked}

    # Best single fix: highest simulation gain hint among unblocked controls
    best_single = next(
        (s for s in simulations if s["id"] not in blocked_ids),
        simulations[0] if simulations else None,
    )

    # Best 30-day bundle: top 5 unblocked controls by ROI
    bundle = [_slim_finding(f) for f in findings_by_roi if f["id"] not in blocked_ids][:5]

    # Weakest categories: bottom 3 by score
    weakest_categories = sorted(category_scores.items(), key=lambda x: x[1])[:3]

    # Dominant threats already computed in scoring
    dominant_threats = results.get("dominant_threats", [])

    # Confidence notes: findings where the answer was "Don't Know" (treated as worst-case)
    confidence_notes = [
        {
            "id": f["id"],
            "question": f["question"],
            "category": f["category"],
            "note": "Unanswered — scored as worst-case (Don't Know). Actual risk may be lower if control exists.",
        }
        for f in findings_by_roi
        if f["answer"] == "Don't Know"
    ]

    return {
        "organization_name": org_name,
        "organization_type": org_type,
        "organization_size": org_size,
        "overall_score": results["overall_score"],
        "risk_level": results["risk_level"],
        "category_scores": category_scores,
        "top_actions": [
            {
                "question": item["question"],
                "category": item["category"],
                "answer": item["answer"],
                "priority_score": item["roi_score"],
                "remediation": item["remediation"],
                "why_it_matters": item["why_it_matters"],
                "framework_map": item["framework_map"],
            }
            for item in results["top_actions"]
        ],
        "findings_by_roi": [_slim_finding(f) for f in findings_by_roi[:10]],
        "quick_wins": [_slim_finding(f) for f in quick_wins[:5]],
        "dominant_threats": dominant_threats,
        "weakest_categories": [{"category": c, "score": s} for c, s in weakest_categories],
        "best_single_fix_simulation": best_single,
        "best_30_day_bundle": bundle,
        "blocked_by_dependencies": blocked,
        "org_type_specific_notes": _ORG_TYPE_NOTES.get(
            org_type,
            f"Assess controls in the context of a {org_type or 'general'} organization's regulatory and threat landscape.",
        ),
        "confidence_notes": confidence_notes,
    }


def generate_demo_report(payload: Dict) -> str:
    actions = payload["top_actions"]
    quick_wins = payload.get("quick_wins", [])
    bundle = payload.get("best_30_day_bundle", [])
    best_single = payload.get("best_single_fix_simulation")
    weakest = payload.get("weakest_categories", [])
    dominant_threats = payload.get("dominant_threats", [])
    confidence_notes = payload.get("confidence_notes", [])

    weakest_text = ", ".join([f"{c['category']} ({c['score']}/100)" for c in weakest])
    threats_text = ", ".join(dominant_threats) if dominant_threats else "ransomware, credential theft"

    lines = []

    lines.append(
        f"Executive Summary\n"
        f"{payload['organization_name']} scored {payload['overall_score']}/100 — a {payload['risk_level']} risk posture. "
        f"Weakest areas: {weakest_text}. "
        f"Top active threat vectors: {threats_text}."
    )
    if confidence_notes:
        lines.append(
            f"Note: {len(confidence_notes)} control(s) were unanswered and scored as worst-case (\"Don't Know\"). "
            "Revisit these to refine the score."
        )

    if actions:
        top = actions[0]
        lines.append(
            f"Biggest Risk Right Now\n"
            f"{top['category']}: {top['why_it_matters']} "
            f"Remediation: {top['remediation']}"
        )

    if quick_wins:
        qw = quick_wins[0]
        lines.append(
            f"Best Quick Win\n"
            f"{qw['remediation']} — effort: {qw['effort']}, value in: {qw['time_to_value']}. "
            f"Addresses: {', '.join(qw['threats'][:2])}."
        )
    elif actions:
        qw = actions[0]
        lines.append(
            f"Best Quick Win\n"
            f"{qw['remediation']} — tackles the highest-priority unresolved gap."
        )

    if bundle:
        lines.append("Best 30-Day Plan")
        for idx, item in enumerate(bundle, start=1):
            lines.append(f"Week {idx}: {item['remediation']} ({item['category']}, effort: {item['effort']})")
    else:
        lines.append("Best 30-Day Plan")
        for idx, item in enumerate(actions, start=1):
            lines.append(f"Week {idx}: {item['remediation']}")

    if best_single:
        lines.append(
            f"What If You Fix One Thing?\n"
            f"Fixing \"{best_single['question']}\" could improve your score by up to "
            f"{best_single['simulation_gain_hint']} points — the highest single-control gain available."
        )

    lines.append(
        f"Why These Actions Matter\n"
        f"The controls above target the gaps most likely to result in an incident for a "
        f"{payload['organization_type'] or 'general'} organization of your size. "
        f"{payload.get('org_type_specific_notes', '')}"
    )

    lines.append("Framework Traceability")
    for item in actions[:3]:
        lines.append(f"- {item['question'][:60]}… → {item['framework_map']}")

    return "\n\n".join(lines)


def generate_ai_report(payload: Dict) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return generate_demo_report(payload)

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a cyber risk triage agent for non-technical organizations. "
        "You must reason only from the provided JSON. "
        "Prioritize actions by likely risk reduction, effort, and speed to value. "
        "Explain tradeoffs in plain language. "
        "Always identify: biggest risk, best quick win, best 30-day plan, and what changes the score most."
    )

    user_prompt = (
        "Analyze the assessment JSON below and produce a structured report with exactly these sections:\n\n"
        "1. Executive Summary — 2–3 sentences: overall posture, score, risk level, top threat vectors.\n"
        "2. Biggest Risk Right Now — the single highest-impact unresolved control and why it matters.\n"
        "3. Best Quick Win — the fastest, lowest-effort action with meaningful risk reduction. Include effort and time-to-value.\n"
        "4. Best 30-Day Plan — a week-by-week sequence of the top unblocked controls from best_30_day_bundle.\n"
        "5. What If You Fix One Thing? — use best_single_fix_simulation to explain the score impact of the highest-gain control.\n"
        "6. Why These Actions Matter — connect the recommended actions to the org-type context and dominant threats. "
        "Note any confidence_notes items and how they affect certainty.\n"
        "7. Framework Traceability — for each top action, cite the framework_map reference.\n\n"
        f"Assessment JSON:\n{json.dumps(payload, indent=2)}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content
