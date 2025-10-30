# Star Signal (Next)

Minimal refactor using **Visual Crossing** as the single data source.
- One call yields hourly weather + daily sunrise/sunset + moon rise/set + moon phase.
- Scoring pipeline preserved: we reuse your `utils.py` with weights & logistic params intact.
- Pushover notifications unchanged.

## Setup
1) `pip install -r requirements.txt`
2) Edit `config.py`:
   - `VISUAL_CROSSING_API_KEY` (free account)
   - `USERS` Pushover keys
   - `LOCATIONS` lat,lon

## Run
```
python -m src.main
```

## Notes
- Provider: `src/provider_vc.py` -> returns rows matching your existing field names.
- We keep per-hour rows; `main.py` aggregates by day and alerts when max score >= threshold.
- To switch providers later, replace `fetch_visualcrossing` with an Open-Meteo-based function and keep the same output keys.