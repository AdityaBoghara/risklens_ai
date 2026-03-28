from typing import Dict, List

from scoring import calculate_results


def _threats_reduced(before_findings: List[Dict], after_findings: List[Dict]) -> List[str]:
    """Return threat tags that disappeared from findings after the simulated fix."""
    before_ids = {f["id"] for f in before_findings}
    after_ids = {f["id"] for f in after_findings}
    resolved_ids = before_ids - after_ids
    seen = set()
    reduced = []
    for f in before_findings:
        if f["id"] in resolved_ids:
            for t in f["threats"]:
                if t not in seen:
                    seen.add(t)
                    reduced.append(t)
    return reduced


def _category_deltas(before_scores: Dict[str, int], after_scores: Dict[str, int]) -> Dict[str, int]:
    return {
        cat: after_scores[cat] - before_scores[cat]
        for cat in before_scores
        if after_scores[cat] != before_scores[cat]
    }


def simulate_fix(answers: Dict[str, str], question_id: str, org_type: str = "") -> Dict:
    """Simulate resolving a single control and return the score impact."""
    before = calculate_results(answers, org_type)

    patched = {**answers, question_id: "Yes"}
    after = calculate_results(patched, org_type)

    return {
        "question_id": question_id,
        "score_before": before["overall_score"],
        "score_after": after["overall_score"],
        "score_delta": after["overall_score"] - before["overall_score"],
        "risk_level_before": before["risk_level"],
        "risk_level_after": after["risk_level"],
        "risk_level_changed": before["risk_level"] != after["risk_level"],
        "category_deltas": _category_deltas(before["category_scores"], after["category_scores"]),
        "threats_reduced": _threats_reduced(before["findings"], after["findings"]),
    }


def simulate_top_fixes(answers: Dict[str, str], org_type: str = "", limit: int = 5) -> List[Dict]:
    """
    Simulate fixing each failing control independently and rank by score delta.
    Returns up to `limit` results, highest-impact first.
    """
    before = calculate_results(answers, org_type)
    failing_ids = [f["id"] for f in before["findings"]]

    results = []
    for qid in failing_ids:
        sim = simulate_fix(answers, qid, org_type)
        sim["question"] = next(f["question"] for f in before["findings"] if f["id"] == qid)
        sim["roi_score"] = next(f["roi_score"] for f in before["findings"] if f["id"] == qid)
        sim["quick_win"] = next(f["quick_win"] for f in before["findings"] if f["id"] == qid)
        results.append(sim)

    results.sort(key=lambda x: (x["score_delta"], x["roi_score"]), reverse=True)
    return results[:limit]


def simulate_bundle(answers: Dict[str, str], question_ids: List[str], org_type: str = "") -> Dict:
    """
    Simulate resolving a set of controls together and return the combined impact.
    Useful for showing the effect of an initiative (e.g. 'fix all Access Control gaps').
    """
    before = calculate_results(answers, org_type)

    patched = {**answers, **{qid: "Yes" for qid in question_ids}}
    after = calculate_results(patched, org_type)

    return {
        "question_ids": question_ids,
        "score_before": before["overall_score"],
        "score_after": after["overall_score"],
        "score_delta": after["overall_score"] - before["overall_score"],
        "risk_level_before": before["risk_level"],
        "risk_level_after": after["risk_level"],
        "risk_level_changed": before["risk_level"] != after["risk_level"],
        "category_deltas": _category_deltas(before["category_scores"], after["category_scores"]),
        "threats_reduced": _threats_reduced(before["findings"], after["findings"]),
        "remaining_findings": len(after["findings"]),
    }
