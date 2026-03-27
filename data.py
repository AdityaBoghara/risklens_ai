import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

_DATA = json.loads((Path(__file__).parent / "questions.json").read_text())


@dataclass
class Question:
    id: str
    text: str
    category: str
    weight: int
    impact: float
    remediation: str
    why_it_matters: str
    framework_map: str


QUESTIONS: List[Question] = [Question(**q) for q in _DATA["questions"]]

ANSWER_FACTORS: Dict[str, float] = _DATA["answer_factors"]

URGENCY_FACTORS: Dict[str, float] = _DATA["urgency_factors"]

CATEGORY_ORDER: List[str] = _DATA["category_order"]

# Per-org-type weight overrides: only questions that differ from the baseline are listed.
# Clinics must protect patient data (HIPAA) → elevate Data Protection and device encryption.
# Schools face heavy phishing exposure and handle student records → elevate training and data controls.
# Nonprofits are often under-resourced with no dedicated security owner → elevate governance and IR.
# Startups move fast and accumulate patch debt quickly → elevate Patch Management.
ORG_TYPE_WEIGHT_OVERRIDES: Dict[str, Dict[str, int]] = _DATA["org_type_weight_overrides"]
