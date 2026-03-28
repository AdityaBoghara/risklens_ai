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

    # Derive plan depth and section verbosity from org size
    _plan_depth = {
        "1-10": {"plan_items": 2, "section_sentences": 2, "tool_specificity": "free or built-in tools only"},
        "11-50": {"plan_items": 3, "section_sentences": 3, "tool_specificity": "named SaaS products where possible"},
        "51-200": {"plan_items": 4, "section_sentences": 4, "tool_specificity": "named products and brief team coordination note"},
        "201-1000": {"plan_items": 5, "section_sentences": 5, "tool_specificity": "named products, procurement path, and owner role"},
        "1000+": {"plan_items": 5, "section_sentences": 5, "tool_specificity": "named products, owner role, and governance/audit implication"},
    }
    depth = _plan_depth.get(org_size, {"plan_items": 3, "section_sentences": 3, "tool_specificity": "named tools where possible"})
    plan_items_n = depth["plan_items"]
    section_sentences = depth["section_sentences"]
    tool_specificity = depth["tool_specificity"]

    system_prompt = (
        f"You are a cyber risk triage advisor — not a report writer. "
        f"Your job is to make hard prioritization calls and tell the organization exactly what to do next, in order. "
        f"You are advising a {org_type} organization with {org_size} employees.\n\n"
        f"ORG TYPE CONTEXT: {org_type_notes}\n\n"
        f"ORG SIZE CONTEXT: {org_size_notes}\n\n"
        f"TRIAGE RULES YOU MUST FOLLOW:\n"
        f"- Reason only from the provided JSON data. Do not invent controls or threats not present in the data.\n"
        f"- Make a single committed decision in every section — never list alternatives or say 'it depends'.\n"
        f"- Use plain language. A non-technical executive must be able to act on this immediately.\n"
        f"- The dominant threats for this org are: {dominant_threats}. Every priority decision must connect back to these threats.\n"
        f"- If a control is in blocked_by_dependencies, never recommend it before its blocker.\n\n"
        f"PRIORITIZATION ORDERING (apply in every ranked list):\n"
        f"  Primary key:   roi_score descending\n"
        f"  Tiebreaker 1: simulation_gain_hint descending\n"
        f"  Tiebreaker 2: effort ascending (Low < Medium < High)\n"
        f"  Always surface unblocked controls before blocked ones.\n\n"
        f"SPECIFICITY FLOOR — every remediation step must name {tool_specificity}. "
        f"Do not write 'enable MFA'; write 'enable MFA in [product] via [specific setting path]'. "
        f"Do not write 'improve patching'; write 'configure automatic OS updates in [product] and verify with [check]'.\n\n"
        f"ORG-SIZE OUTPUT CALIBRATION for {org_size} employees:\n"
        f"  - Each narrative section: {section_sentences} sentences maximum.\n"
        f"  - 30-Day Plan: exactly {plan_items_n} items (do not pad with lower-ROI items to reach 5).\n"
        f"  - If org_size is '1-10': every action must be completable solo in under one day; omit anything requiring procurement or dedicated staff.\n"
        f"  - If org_size is '11-50': every action must be deliverable by one part-time IT contact or an MSP; flag anything requiring a dedicated hire.\n"
        f"  - If org_size is '51-200': actions may require multi-day effort but must fit within existing IT bandwidth; note if a vendor engagement is needed.\n"
        f"  - If org_size is '201-1000' or '1000+': governance, compliance, and cross-team coordination details are expected."
    )

    confidence_count = len(payload.get("confidence_notes", []))

    user_prompt = (
        "Triage the assessment JSON below. Produce output with EXACTLY these six sections in this order — no extras, no reordering.\n\n"
        "## Biggest Risk Right Now\n"
        f"Select the single unresolved control with the highest roi_score among unblocked findings. "
        f"If two controls tie on roi_score, pick the one with the higher simulation_gain_hint; if still tied, pick lower effort. "
        f"Write {section_sentences} sentences maximum: name the specific control (not the category), "
        f"state the roi_score and simulation_gain_hint from the JSON, "
        f"identify which dominant threat it directly enables, "
        f"and state the concrete business consequence (data breach / downtime / regulatory fine) if left unresolved. "
        f"Do not use the word 'risk' as a noun — name the actual threat actor behaviour.\n\n"
        "## Best Quick Win\n"
        f"Select the top-ranked item from quick_wins (highest roi_score, unblocked). "
        f"Write {section_sentences} sentences maximum. "
        f"State: the exact remediation step with {tool_specificity}, effort level from the JSON, "
        f"time-to-value from the JSON, and the specific threat tag(s) it removes. "
        f"Do not recommend this action if it appears in blocked_by_dependencies — pick the next unblocked quick_win instead.\n\n"
        "## Best 30-Day Plan\n"
        f"Draw exactly {plan_items_n} items from best_30_day_bundle, ordered by roi_score descending "
        f"(tiebreak: simulation_gain_hint desc, effort asc). "
        f"Do not include more than {plan_items_n} items even if the bundle has more. "
        f"Format each item as: 'Week N — [control name]: [specific remediation step with {tool_specificity}] "
        f"(effort: X, closes: [threat tag])'. "
        f"If a control is in blocked_by_dependencies, move it after the item that unblocks it and note '(requires Week M first)'. "
        f"Each week must build on the previous — no item may assume capabilities not established by prior weeks.\n\n"
        "## Highest-Impact Fix\n"
        f"Use best_single_fix_simulation. Name the control exactly as it appears in the JSON. "
        f"State the simulation_gain_hint point gain. "
        f"In {min(section_sentences, 3)} sentences: explain why this control has outsized leverage "
        f"(i.e., what downstream controls it unblocks or what threats it severs at the root). "
        f"If this control is in blocked_by_dependencies, name the blocker and state what must be done first.\n\n"
        "## Why These Actions Matter\n"
        f"Write exactly {section_sentences} sentences. "
        f"Sentence 1: connect the #1 risk to the specific threat landscape in org_type_specific_notes. "
        f"Sentence 2: explain why the 30-day sequence is ordered correctly for a {org_size}-person org "
        f"(reference the capacity constraint in org_size_specific_notes). "
        f"Sentence 3: name the dominant_threats from the JSON and explain how the full plan dismantles them. "
        + (f"Sentences 4–{section_sentences}: governance and compliance framing relevant to {org_type}. " if section_sentences > 3 else "")
        + "Do not repeat content from other sections — synthesize it.\n\n"
        "## Confidence / Unknowns\n"
        + (
            f"There are {confidence_count} controls in confidence_notes answered 'Don't Know'. "
            f"For each one write exactly three lines:\n"
            f"  - Control: [name] | Category: [category]\n"
            f"  - If already in place: [what the score overstatement is — which category score would improve and by how much]\n"
            f"  - Resolution: [one concrete step to confirm within 5 business days, using {tool_specificity}]\n"
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
