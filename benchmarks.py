"""
Prototype benchmark baselines for RiskLens AI.

Derived from expert heuristics and assessment design assumptions — not from
external survey data.  The sector weighting encoded in ORG_TYPE_WEIGHT_OVERRIDES
informs each sector's expected posture: categories with higher weights are
typically the ones small orgs in that sector under-invest in relative to their
actual exposure, which depresses average scores in those areas.

These baselines are presented as indicative prototypes for hackathon purposes.
"""

from typing import Dict, List

# Keys must match the category_order in questions.json and the selectbox values
# in app.py.  "Other" falls back to the Small Business baseline.

ORG_BASELINES: Dict[str, Dict] = {
    "Small Business": {
        "overall": 52,
        "category_scores": {
            "Access Control": 50,
            "Endpoint Security": 55,
            "Data Protection": 48,
            "Patch Management": 53,
            "Backup & Recovery": 56,
            "Incident Response": 45,
        },
        "common_weak_spots": ["Incident Response", "Data Protection", "Access Control"],
    },
    "School": {
        "overall": 48,
        "category_scores": {
            "Access Control": 45,
            "Endpoint Security": 52,
            "Data Protection": 44,
            "Patch Management": 50,
            "Backup & Recovery": 55,
            "Incident Response": 42,
        },
        "common_weak_spots": ["Incident Response", "Data Protection", "Access Control"],
    },
    "Clinic": {
        "overall": 55,
        "category_scores": {
            "Access Control": 60,
            "Endpoint Security": 50,
            "Data Protection": 58,
            "Patch Management": 52,
            "Backup & Recovery": 60,
            "Incident Response": 48,
        },
        "common_weak_spots": ["Incident Response", "Endpoint Security", "Patch Management"],
    },
    "Nonprofit": {
        "overall": 44,
        "category_scores": {
            "Access Control": 42,
            "Endpoint Security": 46,
            "Data Protection": 40,
            "Patch Management": 44,
            "Backup & Recovery": 50,
            "Incident Response": 38,
        },
        "common_weak_spots": ["Incident Response", "Data Protection", "Access Control"],
    },
    "Startup": {
        "overall": 57,
        "category_scores": {
            "Access Control": 62,
            "Endpoint Security": 60,
            "Data Protection": 52,
            "Patch Management": 58,
            "Backup & Recovery": 53,
            "Incident Response": 49,
        },
        "common_weak_spots": ["Incident Response", "Data Protection", "Backup & Recovery"],
    },
}

# Fallback for org types not listed above (e.g. "Other")
_FALLBACK = ORG_BASELINES["Small Business"]


def get_baseline(org_type: str) -> Dict:
    """Return the baseline dict for *org_type*, falling back to Small Business."""
    return ORG_BASELINES.get(org_type, _FALLBACK)


def peer_comparison(org_type: str, category_scores: Dict[str, int]) -> List[Dict]:
    """
    Compare *category_scores* against the sector baseline.

    Returns a list of dicts, one per category:
        {
            "category": str,
            "org_score": int,
            "baseline_score": int,
            "delta": int,          # positive = above baseline
            "status": "above" | "on-par" | "below",
        }

    "on-par" means within ±3 points of the baseline.
    """
    baseline = get_baseline(org_type)
    baseline_cats = baseline["category_scores"]
    result = []
    for category, org_score in category_scores.items():
        b_score = baseline_cats.get(category, baseline["overall"])
        delta = org_score - b_score
        if delta > 3:
            status = "above"
        elif delta < -3:
            status = "below"
        else:
            status = "on-par"
        result.append(
            {
                "category": category,
                "org_score": org_score,
                "baseline_score": b_score,
                "delta": delta,
                "status": status,
            }
        )
    return result
