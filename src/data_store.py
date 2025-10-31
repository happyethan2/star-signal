import csv
from pathlib import Path
from typing import Iterable, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_PATH = DATA_DIR / "forecast_history.csv"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_forecast_history(
    city: str,
    run_timestamp_iso: str,
    scored_days: Iterable[dict],
    promise_window: Optional[str],
) -> None:
    _ensure_data_dir()
    fieldnames = [
        "run_timestamp",
        "location",
        "promise_window",
        "forecast_date",
        "suitability_score",
        "avg_cloud",
        "min_cloud",
        "max_cloud",
        "moon_presence",
        "moon_illumination",
        "wind_speed_kph",
        "humidity",
        "visibility_km",
    ]

    file_exists = HISTORY_PATH.exists()
    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for day in scored_days:
            writer.writerow(
                {
                    "run_timestamp": run_timestamp_iso,
                    "location": city,
                    "promise_window": promise_window or "",
                    "forecast_date": day.get("date", ""),
                    "suitability_score": day.get("suitability_score", ""),
                    "avg_cloud": day.get("avg_cloud", ""),
                    "min_cloud": day.get("min_cloud", ""),
                    "max_cloud": day.get("max_cloud", ""),
                    "moon_presence": day.get("moon_presence", ""),
                    "moon_illumination": day.get("moon_illumination", ""),
                    "wind_speed_kph": day.get("wind_speed_kph", ""),
                    "humidity": day.get("humidity", ""),
                    "visibility_km": day.get("visibility_km", ""),
                }
            )
