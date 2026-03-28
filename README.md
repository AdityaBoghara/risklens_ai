# RiskLens AI

Cyber risk assessment assistant for small organizations — built for HackMISSO 2026.

## What it does
- Runs a structured cybersecurity questionnaire tailored to your sector
- Calculates an overall risk score and per-category scores with sector-aware weighting
- Ranks remediation actions by ROI (impact vs. effort) for actionable prioritization
- Simulates "what if we fix this?" to show score improvements before committing resources
- Compares your posture against peer baselines for clinics, schools, nonprofits, startups, and small businesses
- Generates an AI triage report with plain-language reasoning and a 30-day action plan
- Tracks assessment history and surfaces narrative trends across runs
- Exports results to CSV

## Stack
- Streamlit
- Pure Python scoring and simulation engine
- OpenAI API (optional) — for AI-generated reports
- python-dotenv

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Environment variables
Use either shell export or a `.env` file in the project root.

Option 1 (shell):
```bash
export OPENAI_API_KEY=your_key_here
```

Option 2 (dotenv file `.env`):
```dotenv
OPENAI_API_KEY=your_key_here
```

The app loads `.env` automatically via `python-dotenv`. Without an API key it falls back to a deterministic demo report.

## Core design
- Deterministic scoring for transparency
- ROI-aware prioritization for action sequencing
- Simulation engine for "what should we fix first"
- AI triage agent for plain-language reasoning and 30-day planning
- Sector-aware weighting for clinics, schools, nonprofits, and startups

## Demo flow
1. Answer assessment
2. Review risk dashboard
3. Inspect biggest risk
4. Simulate one fix
5. Compare peer baseline
6. Read AI-generated action plan

## Files
- `app.py` — Streamlit UI and app orchestration
- `scoring.py` — weighted scoring engine and ROI prioritization
- `simulator.py` — fix simulation and score-delta calculations
- `benchmarks.py` — sector peer baselines
- `history.py` — assessment history persistence
- `report.py` — AI report generation and LLM payload builder
- `data.py` — questions, category definitions, and org-type weight overrides
- `questions.json` — question bank
- `requirements.txt` — dependencies
