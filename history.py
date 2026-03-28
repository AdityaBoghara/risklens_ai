import json
import os
from datetime import date
from typing import Dict, Optional

HISTORY_FILE = "assessment_history.json"


def _load() -> Dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def _save(data: Dict) -> None:
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_all_assessments(org_name: str) -> list:
    """Return all saved assessments for org_name in chronological order."""
    data = _load()
    return data.get(org_name, [])


def get_last_assessment(org_name: str) -> Optional[Dict]:
    """Return the most recent saved assessment for org_name, or None."""
    data = _load()
    entries = data.get(org_name, [])
    return entries[-1] if entries else None


def save_assessment(org_name: str, org_type: str, org_size: str, results: Dict) -> None:
    """Append today's assessment to the history for org_name."""
    data = _load()
    top_actions = results.get("top_actions", [])
    quick_wins = results.get("quick_wins", [])
    entry = {
        "date": date.today().isoformat(),
        "org_type": org_type,
        "org_size": org_size,
        "overall_score": results["overall_score"],
        "risk_level": results["risk_level"],
        "category_scores": results["category_scores"],
        # Narrative fields
        "top_action_ids": [a["id"] for a in top_actions],
        "top_action_categories": [a["category"] for a in top_actions],
        "dominant_threats": results.get("dominant_threats", []),
        "best_quick_win_id": quick_wins[0]["id"] if quick_wins else None,
        "best_quick_win_label": quick_wins[0]["category"] if quick_wins else None,
    }
    data.setdefault(org_name, []).append(entry)
    _save(data)
