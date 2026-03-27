import json
import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


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
