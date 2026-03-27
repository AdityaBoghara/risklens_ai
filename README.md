# RiskLens AI

A lightweight cyber risk assessment system for hackathon delivery.

## What it does
- Runs a structured cybersecurity questionnaire
- Calculates an overall score and category scores
- Ranks the highest-priority remediation actions
- Generates a readable AI report using OpenAI when `OPENAI_API_KEY` is set
- Falls back to a deterministic demo report when no API key is present

## Stack
- Streamlit
- Pure Python scoring engine
- Optional OpenAI API integration

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

The app now loads environment variables from `.env` automatically with `python-dotenv`.

## Core design
- Deterministic weighted scoring engine
- Rule-based prioritization
- LLM used only for explanation, not scoring

## Files
- `app.py` — full application
- `requirements.txt` — dependencies
- `README.md` — setup instructions
