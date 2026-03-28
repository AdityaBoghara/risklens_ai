import json
import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_ORG_SIZE_CONTEXT = {
    "1-10": (
        "This is a micro-organization with no dedicated security staff. "
        "Recommendations must be executable by a non-technical owner or a single IT generalist. "
        "Favor free/low-cost tools, cloud-managed solutions, and controls that require no ongoing maintenance. "
        "Complexity is the enemy — every action must be completable in under a day."
    ),
    "11-50": (
        "This is a small organization, likely with one part-time IT person or a managed service provider. "
        "Favor controls with vendor support or SaaS delivery. "
        "Avoid recommendations requiring dedicated security headcount. "
        "Prioritize identity and email controls — the attack surface is small but the blast radius of a breach is high."
    ),
    "51-200": (
        "This is a mid-size organization with some IT capacity but limited security expertise. "
        "Controls should be implementable within existing IT bandwidth. "
        "Segmentation and logging become feasible here. "
        "Emphasize quick wins that do not require procurement cycles."
    ),
    "201-1000": (
        "This organization has dedicated IT and may have a part-time security function. "
        "More advanced controls (SIEM, EDR, PAM) are realistic. "
        "Prioritize controls that scale across teams and don't require per-user manual steps. "
        "Compliance obligations likely apply — tie recommendations to framework mappings."
    ),
    "1000+": (
        "This is a large organization with a formal IT and security team. "
        "Focus recommendations on gaps in governance, detection, and response — not basic hygiene. "
        "Assume basic controls (AV, firewall, patching) exist unless the data shows otherwise. "
        "Emphasize third-party risk, privileged access, and audit trail completeness."
    ),
}

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
        "urgency": item["urgency"],
        "remediation": item["remediation"],
        "why_it_matters": item["why_it_matters"],
        "business_impact": item["business_impact"],
        "follow_up_if_no": item["follow_up_if_no"],
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
        "org_size_specific_notes": _ORG_SIZE_CONTEXT.get(
            org_size,
            f"Tailor recommendations to the capacity and resource constraints of a {org_size or 'general'} organization.",
        ),
        "confidence_notes": confidence_notes,
    }


def generate_demo_report(payload: Dict) -> str:
    actions = payload["top_actions"]
    quick_wins = payload.get("quick_wins", [])
    bundle = payload.get("best_30_day_bundle", [])
    best_single = payload.get("best_single_fix_simulation")
    dominant_threats = payload.get("dominant_threats", [])
    confidence_notes = payload.get("confidence_notes", [])
    blocked = payload.get("blocked_by_dependencies", [])
    org_type = payload.get("organization_type") or "general"
    org_size = payload.get("organization_size") or "unknown"

    threats_text = ", ".join(dominant_threats) if dominant_threats else "ransomware, credential theft"
    blocked_ids = {b["id"] for b in blocked}

    lines = []

    # Biggest Risk Right Now
    if actions:
        top = actions[0]
        lines.append(
            f"## Biggest Risk Right Now\n"
            f"[{top['category']}] {top['why_it_matters']} "
            f"For a {org_type} organization of {org_size}, this gap directly exposes you to {threats_text}. "
            f"Recommended action: {top['remediation']}"
        )

    # Best Quick Win
    if quick_wins:
        qw = quick_wins[0]
        lines.append(
            f"## Best Quick Win\n"
            f"{qw['remediation']} — effort: {qw['effort']}, time-to-value: {qw['time_to_value']}. "
            f"Directly reduces: {', '.join(qw['threats'][:2])}. "
            f"Appropriate for a {org_size} team with no dedicated security staff."
        )
    elif actions:
        qw = actions[0]
        lines.append(
            f"## Best Quick Win\n"
            f"{qw['remediation']} — tackles the highest-priority unresolved gap with available capacity."
        )

    # Best 30-Day Plan
    plan_items = bundle if bundle else actions
    plan_lines = ["## Best 30-Day Plan"]
    for idx, item in enumerate(plan_items, start=1):
        effort = item.get("effort", "—")
        item_threats = item.get("threats", [])
        threat_str = f" | closes: {', '.join(item_threats[:2])}" if item_threats else ""
        blocked_note = " ⚠ blocked — complete dependency first" if item.get("id") in blocked_ids else ""
        plan_lines.append(
            f"  Week {idx}: {item['remediation']} ({item['category']}, effort: {effort}{threat_str}{blocked_note})"
        )
    lines.append("\n".join(plan_lines))

    # Highest-Impact Fix
    if best_single:
        lines.append(
            f"## Highest-Impact Fix\n"
            f"Fixing \"{best_single['question']}\" could improve your score by up to "
            f"{best_single['simulation_gain_hint']} points — the largest single-control gain available. "
            f"This control has outsized leverage relative to its effort because it addresses the root cause "
            f"behind multiple scored gaps."
        )

    # Why These Actions Matter
    if actions:
        top = actions[0]
        lines.append(
            f"## Why These Actions Matter\n"
            f"These recommendations are calibrated for a {org_type} organization of {org_size}. "
            f"{payload.get('org_type_specific_notes', '')} "
            f"{payload.get('org_size_specific_notes', '')} "
            f"The sequencing prioritizes controls that close {threats_text} exposure first, "
            f"then layers in controls that require more time or resources."
        )

    # Confidence / Unknowns
    if confidence_notes:
        caveat_lines = [f"## Confidence / Unknowns\n{len(confidence_notes)} control(s) were answered 'Don't Know' and scored as worst-case. Your actual risk may be lower."]
        for cn in confidence_notes:
            caveat_lines.append(
                f"  - [{cn['category']}] \"{cn['question'][:80]}\"\n"
                f"    If this control already exists: the risk score for this area is likely overstated.\n"
                f"    Action (within 5 business days): confirm with your IT team whether this control is active and update the assessment."
            )
        lines.append("\n".join(caveat_lines))
    else:
        lines.append("## Confidence / Unknowns\nAll controls were answered — no confidence gaps to report.")

    return "\n\n".join(lines)


def generate_ai_report(payload: Dict) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return generate_demo_report(payload)

    client = OpenAI(api_key=api_key)

    org_type = payload.get("organization_type") or "general"
    org_size = payload.get("organization_size") or "unknown"
    org_type_notes = payload.get("org_type_specific_notes", "")
    org_size_notes = payload.get("org_size_specific_notes", "")
    dominant_threats = ", ".join(payload.get("dominant_threats", [])) or "ransomware, credential theft"

    system_prompt = (
        f"You are a cyber risk triage advisor — not a report writer. "
        f"Your job is to make hard prioritization calls and tell the organization exactly what to do next, in order. "
        f"You are advising a {org_type} organization with {org_size} employees.\n\n"
        f"ORG TYPE CONTEXT: {org_type_notes}\n\n"
        f"ORG SIZE CONTEXT: {org_size_notes}\n\n"
        f"TRIAGE RULES YOU MUST FOLLOW:\n"
        f"- Reason only from the provided JSON data. Do not invent controls or threats not present in the data.\n"
        f"- Make a single committed decision in every section — never list alternatives or say 'it depends'.\n"
        f"- Calibrate every recommendation to the capacity of a {org_size}-person {org_type} organization.\n"
        f"- Use plain language. Avoid jargon. A non-technical executive must be able to act on this immediately.\n"
        f"- The dominant threats for this org are: {dominant_threats}. Every priority decision must connect back to these threats.\n"
        f"- If a control is blocked by a dependency, do not recommend it as a first action."
    )

    confidence_count = len(payload.get("confidence_notes", []))

    user_prompt = (
        "Triage the assessment JSON below. Produce output with EXACTLY these six sections — no extras, no reordering.\n\n"
        "## Biggest Risk Right Now\n"
        "Name the single unresolved control that poses the greatest threat to this specific org type and size. "
        "In 2–3 sentences: what is the control, why does it rank #1 given the dominant threats, "
        "and what is the business consequence if it is not addressed?\n\n"
        "## Best Quick Win\n"
        "Name one action the org can complete this week with minimal effort. "
        "State: what it is, effort level, time-to-value, and which specific threat it removes. "
        "Calibrate 'minimal effort' to the org's size — do not recommend actions requiring dedicated security staff "
        "if the org has fewer than 50 employees.\n\n"
        "## Best 30-Day Plan\n"
        "Provide a week-by-week action sequence drawn from best_30_day_bundle. "
        "For each week: name the control, state effort, state the threat it closes. "
        "Sequence these so each week builds on the last (dependency order). "
        "If a control is in blocked_by_dependencies, move it after its blocker.\n\n"
        "## Highest-Impact Fix\n"
        "Use best_single_fix_simulation. Name the single control whose remediation would produce the largest "
        "score improvement. State the projected point gain and why that control has outsized leverage "
        "relative to its effort.\n\n"
        "## Why These Actions Matter\n"
        "In 3–5 sentences: connect the recommended actions to the specific threat landscape of a "
        f"{org_type} organization of {org_size} employees. Reference the org_type_specific_notes and "
        "org_size_specific_notes from the JSON. Explain why the sequencing is correct for this org's capacity.\n\n"
        "## Confidence / Unknowns\n"
        + (
            f"There are {confidence_count} controls answered 'Don't Know' in confidence_notes. "
            "For each one, write:\n"
            "- Control name and category\n"
            "- What the actual risk exposure is IF the control already exists (i.e., score may be inflated)\n"
            "- One concrete action to resolve the uncertainty within 5 business days\n"
            if confidence_count > 0
            else "All controls were answered — no confidence gaps to report.\n"
        )
        + f"\nAssessment JSON:\n{json.dumps(payload, indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception:
        return generate_demo_report(payload)
