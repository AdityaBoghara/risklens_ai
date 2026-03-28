# RiskLens AI — Questionnaire & Scoring Matrix

**HackMISSO 2026 Deliverable**
Platform: RiskLens AI — Cybersecurity Risk Assessment for Small Organizations

---

## Overview

RiskLens AI assesses an organization's cybersecurity posture through **18 targeted questions** spanning **6 security categories**. Each question accepts one of four responses: **Yes / Partially / No / Don't Know**. The platform produces a 0–100 risk score, a four-tier risk classification, and a prioritized remediation roadmap tailored to the organization's type.

---

## Section 1: Questionnaire

Questions are grouped by security category and displayed in expandable sections within the platform UI.

---

### Category 1 — Access Control

Controls that govern who can access systems, accounts, and data.

| Q# | Question |
|----|----------|
| Q1 | Do all employees use multi-factor authentication for email and critical systems? |
| Q2 | Are strong unique passwords required or managed with a password manager? |
| Q3 | Are former employees removed from systems promptly after leaving? |
| Q15 | Are admin accounts separate from normal user accounts? |
| Q16 | Do you monitor for suspicious login attempts or unusual account activity? |

---

### Category 2 — Endpoint Security

Controls that protect physical devices from malware, theft, and unauthorized use.

| Q# | Question |
|----|----------|
| Q4 | Are company laptops and desktops protected with antivirus or EDR tools? |
| Q5 | Are company devices encrypted in case they are lost or stolen? |

---

### Category 3 — Patch Management

Controls that ensure systems remain up to date and free of known vulnerabilities.

| Q# | Question |
|----|----------|
| Q6 | Are operating systems and business software updated on a regular schedule? |
| Q7 | Do you track which systems are missing critical security patches? |

---

### Category 4 — Data Protection

Controls that safeguard sensitive business and customer information.

| Q# | Question |
|----|----------|
| Q8 | Is sensitive business or customer data stored securely? |
| Q9 | Is access to sensitive data limited only to people who need it? |
| Q17 | Are third-party tools or vendors reviewed before getting access to business data? |

---

### Category 5 — Backup & Recovery

Controls that ensure data can be recovered after an incident.

| Q# | Question |
|----|----------|
| Q10 | Are important files and systems backed up automatically? |
| Q11 | Are backups tested to confirm they can actually be restored? |

---

### Category 6 — Incident Response

Controls that prepare an organization to detect, report, and recover from cyber incidents.

| Q# | Question |
|----|----------|
| Q12 | Do you have a documented plan for responding to a cyber incident? |
| Q13 | Do employees receive regular cybersecurity awareness training? |
| Q14 | Do employees know how to report phishing or suspicious activity? |
| Q18 | Is there a clearly assigned owner for cybersecurity decisions? |

---

## Section 2: Scoring Model

### 2.1 Answer Factors

Each response maps to two numerical factors used in the risk calculation:

| Response | Answer Factor | Urgency Factor | Rationale |
|----------|--------------|----------------|-----------|
| Yes | 0.0 | 0.0 | Control is in place — no risk contribution |
| Partially | 0.5 | 0.7 | Control partially implemented — moderate exposure |
| No | 1.0 | 1.0 | Control absent — full risk contribution |
| Don't Know | 1.0 | 0.9 | Unknown = uncontrolled; treated nearly equivalent to No |

> "Don't Know" is intentionally penalized heavily. Organizations cannot manage risks they are unaware of.

---

### 2.2 Per-Question Weights & Attributes

Each question carries a **base weight** (relative importance, 1–10), an **impact multiplier** (severity if the control is missing), an **effort rating** (cost to implement), and a **time-to-value** (speed of risk reduction).

| Q# | Category | Base Weight | Impact | Effort | Time-to-Value | Quick Win |
|----|----------|-------------|--------|--------|---------------|-----------|
| Q1 | Access Control | 10 | 1.5× | Medium | Days | No |
| Q2 | Access Control | 8 | 1.2× | Low | Days | Yes |
| Q3 | Access Control | 8 | 1.3× | Low | Days | Yes |
| Q4 | Endpoint Security | 8 | 1.2× | Medium | Days | No |
| Q5 | Endpoint Security | 7 | 1.2× | Low | Days | Yes |
| Q6 | Patch Management | 9 | 1.3× | Medium | Weeks | No |
| Q7 | Patch Management | 8 | 1.2× | Medium | Weeks | No |
| Q8 | Data Protection | 8 | 1.3× | Medium | Weeks | No |
| Q9 | Data Protection | 7 | 1.3× | Medium | Weeks | No |
| Q10 | Backup & Recovery | 10 | 1.4× | Low | Days | Yes |
| Q11 | Backup & Recovery | 9 | 1.4× | Low | Days | Yes |
| Q12 | Incident Response | 9 | 1.3× | Medium | Weeks | No |
| Q13 | Incident Response | 7 | 1.1× | Low | Weeks | Yes |
| Q14 | Incident Response | 7 | 1.1× | Low | Days | Yes |
| Q15 | Access Control | 8 | 1.2× | Medium | Weeks | No |
| Q16 | Access Control | 7 | 1.2× | Medium | Weeks | No |
| Q17 | Data Protection | 5 | 1.1× | Low | Days | Yes |
| Q18 | Incident Response | 6 | 1.1× | Low | Days | Yes |

---

### 2.3 Organization-Type Weight Overrides

Different organizations face different threat profiles. RiskLens AI adjusts question weights at runtime based on the selected organization type.

#### Clinic (HIPAA compliance, patient data sensitivity)
| Question | Base Weight | Adjusted Weight | Reason |
|----------|-------------|-----------------|--------|
| Q8 — Sensitive data storage | 8 | 12 | PHI regulatory exposure |
| Q9 — Least privilege access | 7 | 11 | Insider threat / HIPAA access controls |
| Q5 — Device encryption | 7 | 10 | Mobile device theft risk |
| Q10 — Automated backups | 10 | 12 | Ransomware recovery for clinical operations |
| Q11 — Backup testing | 9 | 11 | Operational continuity requirement |
| Q17 — Vendor review | 5 | 9 | Third-party HIPAA risk (BAAs) |

#### School (High phishing exposure, student records)
| Question | Base Weight | Adjusted Weight | Reason |
|----------|-------------|-----------------|--------|
| Q1 — MFA | 10 | 11 | Staff/student account compromise risk |
| Q8 — Sensitive data storage | 8 | 11 | FERPA student records compliance |
| Q9 — Least privilege | 7 | 10 | Broad user base with varying trust levels |
| Q13 — Security training | 7 | 11 | High phishing click rate in education sector |
| Q14 — Phishing reporting | 7 | 11 | Incident detection depends on user reporting |

#### Nonprofit (Under-resourced, governance gaps)
| Question | Base Weight | Adjusted Weight | Reason |
|----------|-------------|-----------------|--------|
| Q12 — Incident response plan | 9 | 11 | No dedicated IT staff for ad hoc response |
| Q10 — Automated backups | 10 | 11 | Donor/program data continuity |
| Q18 — Security owner | 6 | 10 | Accountability gap in volunteer-led orgs |
| Q13 — Security training | 7 | 9 | High turnover, volunteer workforce |

#### Startup (Rapid growth, technical debt)
| Question | Base Weight | Adjusted Weight | Reason |
|----------|-------------|-----------------|--------|
| Q6 — Patch schedule | 9 | 11 | Move-fast culture leads to deferred patching |
| Q7 — Patch tracking | 8 | 10 | No formal asset management in early stage |
| Q3 — Employee offboarding | 8 | 10 | High employee churn creates orphaned accounts |
| Q17 — Vendor review | 5 | 8 | Heavy SaaS stack with unchecked integrations |

---

### 2.4 Risk Score Per Question

For each question where the answer is not "Yes", a per-question risk score is calculated:

```
risk_score = effective_weight × impact × urgency_factor
```

Where `effective_weight` is the base weight adjusted for organization type.

**Example — Q1 (MFA) answered "No" at a School:**
- Effective weight = 11 (school override from base 10)
- Impact = 1.5×
- Urgency factor = 1.0 (answer: "No")
- **risk_score = 11 × 1.5 × 1.0 = 16.5**

**Example — Q10 (Backups) answered "Partially" at a Clinic:**
- Effective weight = 12 (clinic override from base 10)
- Impact = 1.4×
- Urgency factor = 0.7 (answer: "Partially")
- **risk_score = 12 × 1.4 × 0.7 = 11.76**

---

### 2.5 ROI Score for Recommendation Prioritization

To rank remediation recommendations, each failing control receives an ROI score that balances risk reduction against implementation cost:

```
roi_score = (risk_score × time_to_value_score) / effort_score
```

| Effort Level | Effort Score | Time-to-Value | TTV Score |
|---|---|---|---|
| Low | 1 | Days | 1.2 |
| Medium | 2 | Weeks | 1.0 |
| High | 3 | Months | 0.8 |

A higher ROI score means the control delivers more risk reduction at lower cost — these surface first in the platform's action plan.

**Example — Q2 (Password Manager) answered "No":**
- risk_score = 8 × 1.2 × 1.0 = 9.6
- effort_score = 1 (Low)
- ttv_score = 1.2 (Days)
- **roi_score = (9.6 × 1.2) / 1 = 11.52**

---

## Section 3: Overall Cybersecurity Risk Score Calculation

### 3.1 Formula

The overall score is a **normalized inverse of cumulative risk exposure**, expressed as a 0–100 percentage:

```
total_risk    = Σ (effective_weight × answer_factor)   for all 18 questions
max_risk      = Σ (effective_weight)                   for all 18 questions (worst case: all "No")

overall_score = 100 × (1 − total_risk / max_risk)
```

- All "Yes" answers → **score = 100** (all answer_factors = 0.0, total_risk = 0)
- All "No" answers → **score = 0** (all answer_factors = 1.0, total_risk = max_risk)
- Mixed answers → proportional score reflecting the organization's actual coverage gaps

### 3.2 Risk Level Classification

| Score Range | Risk Level | Interpretation |
|-------------|------------|----------------|
| 80 – 100 | **Low** | Strong baseline controls in place; minor gaps exist |
| 60 – 79 | **Moderate** | Notable gaps present; targeted improvements needed |
| 40 – 59 | **High** | Significant exposure across multiple categories |
| 0 – 39 | **Critical** | Fundamental controls missing; immediate action required |

### 3.3 Category-Level Scores

The same formula is applied independently within each of the 6 categories, producing per-category 0–100 scores used in the radar chart visualization:

```
category_score = 100 × (1 − actual_risk_in_category / max_risk_in_category)
```

This allows organizations to see exactly which domains are weakest and prioritize accordingly.

### 3.4 Control Dependencies

Some controls depend on others being addressed first. The platform tracks these relationships to ensure recommendations are logically sequenced:

| Question | Depends On |
|----------|-----------|
| Q1 — MFA | Q2 (Passwords must be managed before MFA is effective) |
| Q11 — Backup testing | Q10 (Backups must exist before they can be tested) |
| Q15 — Admin separation | Q1, Q2 (Strong auth must precede privilege segmentation) |
| Q16 — Login monitoring | Q1, Q15 (Monitoring is most effective after separation is in place) |

Blocked controls are surfaced in the platform with a note about prerequisites, so organizations tackle the right problems in the right order.

---

## Section 4: Worked Example

**Organization:** A small school with 50 staff members
**Org Type:** School (weight overrides applied)

| Question | Answer | Answer Factor | Effective Weight | Contribution |
|----------|--------|--------------|-----------------|-------------|
| Q1 — MFA | No | 1.0 | 11 | 11.0 |
| Q2 — Passwords | Yes | 0.0 | 8 | 0.0 |
| Q3 — Offboarding | Partially | 0.5 | 8 | 4.0 |
| Q4 — AV/EDR | Yes | 0.0 | 8 | 0.0 |
| Q5 — Encryption | No | 1.0 | 7 | 7.0 |
| Q6 — Patching | Partially | 0.5 | 9 | 4.5 |
| Q7 — Patch tracking | No | 1.0 | 8 | 8.0 |
| Q8 — Data storage | Yes | 0.0 | 11 | 0.0 |
| Q9 — Least privilege | Partially | 0.5 | 10 | 5.0 |
| Q10 — Backups | Yes | 0.0 | 10 | 0.0 |
| Q11 — Backup testing | No | 1.0 | 9 | 9.0 |
| Q12 — IR plan | No | 1.0 | 9 | 9.0 |
| Q13 — Training | No | 1.0 | 11 | 11.0 |
| Q14 — Phishing reporting | Partially | 0.5 | 11 | 5.5 |
| Q15 — Admin separation | Yes | 0.0 | 8 | 0.0 |
| Q16 — Login monitoring | No | 1.0 | 7 | 7.0 |
| Q17 — Vendor review | Yes | 0.0 | 5 | 0.0 |
| Q18 — Security owner | Don't Know | 1.0 | 6 | 6.0 |

```
total_risk  = 11 + 4 + 7 + 4.5 + 8 + 5 + 9 + 9 + 11 + 5.5 + 7 + 6  = 87.0
max_risk    = 11+8+8+8+7+9+8+11+10+10+9+9+11+11+8+7+5+6             = 156.0

overall_score = 100 × (1 − 87.0 / 156.0) = 100 × 0.442 ≈ 44
Risk Level: HIGH
```

**Top Recommendations by ROI:**
1. Q13 — Security Training (roi_score: high, quick win, Low effort, Weeks)
2. Q1 — MFA (roi_score: high, Medium effort, Days)
3. Q12 — Incident Response Plan (Medium effort, Weeks)

---

## Section 5: Framework Alignment

Every finding generated by RiskLens AI includes mapped references to major cybersecurity frameworks, enabling compliance-aware organizations to connect platform recommendations to their existing obligations.

| Framework | Relevant Categories |
|-----------|-------------------|
| **NIST CSF** (Identify, Protect, Detect, Respond, Recover) | All 6 categories |
| **CIS Controls** (Basic, Foundational, Organizational) | Access Control, Endpoint, Patch, Backup |
| **ISO/IEC 27001** (Information Security Management) | Data Protection, Incident Response |
| **HIPAA Security Rule** | Data Protection, Access Control (Clinic org type) |
| **FERPA** | Data Protection (School org type) |

---

*RiskLens AI — HackMISSO 2026*
