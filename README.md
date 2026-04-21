# EndyMed PRO MAX Practice Revenue Planner

This package includes a Streamlit app for internal sales planning.

## Files
- `app.py` — main Streamlit application
- `presets.csv` — frozen preset source of truth
- `requirements.txt` — Python dependencies

## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- Package mode input = monthly new patients starting program
- Per-session mode input = monthly treatments performed
- Fractional and combo consumable logic is already built into the presets
