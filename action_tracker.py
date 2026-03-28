import json
import os
from datetime import date
from typing import Dict

TRACKER_FILE = "action_tracker.json"

STATUS_OPTIONS = ["To Do", "In Progress", "Done"]


def load_tracker(org_name: str) -> Dict[str, Dict]:
    """Return {question_id: {status, updated}} for org_name."""
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r") as f:
        data = json.load(f)
    return data.get(org_name, {})


def save_tracker(org_name: str, tracker: Dict[str, Dict]) -> None:
    """Persist tracker state for org_name."""
    data = {}
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r") as f:
            data = json.load(f)
    data[org_name] = tracker
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def completion_pct(tracker: Dict[str, Dict], all_finding_ids: list) -> int:
    """Percentage of findings marked Done (0–100)."""
    if not all_finding_ids:
        return 0
    done = sum(
        1 for fid in all_finding_ids
        if tracker.get(fid, {}).get("status") == "Done"
    )
    return round(100 * done / len(all_finding_ids))
