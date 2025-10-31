import logging
import sys
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src import pushover_utils as notifs  # noqa: E402
from src import utils  # noqa: E402
from src.data_store import append_forecast_history  # noqa: E402
from src.provider_vc import fetch_visualcrossing  # noqa: E402

logging.basicConfig(
    filename="output.log",
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
)

ADEL_TZ = ZoneInfo("Australia/Adelaide")
WEEKEND_TARGETS = (4, 5)  # Friday, Saturday

# Promise definitions tighten as the week progresses (clouds must look better)
PROMISE_WINDOWS: Dict[str, Dict[str, object]] = {
    "sunday": {
        "weekday": 6,
        "start": time(17, 0),
        "score_min": 0.0,
        "label": "weekend outlook",
    },
    "wednesday": {
        "weekday": 2,
        "start": time(17, 0),
        "score_min": 60.0,
        "label": "mid-week update",
    },
    "thursday": {
        "weekday": 3,
        "start": time(17, 0),
        "score_min": 65.0,
        "label": "thursday confidence",
    },
    "friday": {
        "weekday": 4,
        "start": time(17, 00),
        "score_min": 70.0,
        "label": "final go/no-go",
    },
}


def build_and_score(lat: float, lon: float, days: int = 7) -> List[dict]:
    print(f"[diagnostic] build_and_score: lat={lat} lon={lon} days={days}")
    data = fetch_visualcrossing(lat, lon, days=days)
    logging.info("Fetched data for lat=%.4f lon=%.4f days=%d", lat, lon, days)
    processed = utils.process_weather_data(data)
    scored = utils.add_suitability_scores(processed)
    print(f"[diagnostic] build_and_score: scored_count={len(scored)}")
    return scored


def get_adelaide_now() -> datetime:
    return datetime.now(tz=ADEL_TZ)


def current_promise_window(now: datetime) -> Optional[Tuple[str, Dict[str, object]]]:
    print(f"[diagnostic] current_promise_window: now={now.isoformat()}")
    for label, rule in PROMISE_WINDOWS.items():
        if now.weekday() == rule["weekday"] and now.time() >= rule["start"]:
            print(f"[diagnostic] current_promise_window: matched={label} threshold={rule.get('score_min')}")
            return label, rule
    print("[diagnostic] current_promise_window: no active window")
    return None


def upcoming_weekend_dates(reference: datetime) -> List[datetime.date]:
    targets: List[datetime.date] = []
    for target_weekday in WEEKEND_TARGETS:
        offset = (target_weekday - reference.weekday()) % 7
        target_date = (reference + timedelta(days=offset)).date()
        targets.append(target_date)
    return targets


def _safe_float(value, default: float) -> float:
    try:
        if value is None:
            raise ValueError("None value")
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def select_promising_nights(scored_days, reference, rule):
    print(f"[diagnostic] select_promising_nights: reference={reference.date()} score_min={rule.get('score_min')}")
    by_date = {datetime.strptime(day["date"], "%Y-%m-%d").date(): day for day in scored_days if "date" in day}
    score_min = float(rule.get("score_min", 85.0))
    weekend_dates = upcoming_weekend_dates(reference)
    selections = []

    for target in weekend_dates:
        record = by_date.get(target)
        if not record:
            logging.info("No forecast data for %s", target)
            print(f"[diagnostic] select_promising_nights: missing date={target}")
            continue

        score = float(record.get("suitability_score", 0.0))
        avg_cloud = record.get("avg_cloud")
        moon_presence = record.get("moon_presence")
        print(
            "[diagnostic] select_promising_nights: "
            f"date={record.get('date')} score={score:.1f} avg_cloud={avg_cloud} moon_presence={moon_presence}"
        )
        if score < score_min:
            logging.info("Rejecting %s (score %.1f below %.1f)", record.get("date"), score, score_min)
            print(f"[diagnostic] select_promising_nights: rejected below threshold for {record.get('date')}")
            continue

        selections.append({
            "date": target,
            "score": score,
            "raw": record,
        })

    print(f"[diagnostic] select_promising_nights: selections={len(selections)}")
    return sorted(selections, key=lambda item: item["date"])


def build_promise_message(city: str, rule_label: str, nights: List[dict]) -> str:
    parts = []
    for night in nights:
        day_str = night["date"].strftime("%a %d")
        parts.append(f"{day_str} {night['score']:.0f}% (cloud {night['avg_cloud']:.0f}%)")
    fragment = " | ".join(parts)
    return f"{city} {rule_label} (moonless): {fragment}"


def notify_weekend_promise(
    scored_days: List[dict],
    city: str,
    user_name: str,
    user_key: str,
    now: datetime,
    window: Optional[Tuple[str, Dict[str, object]]] = None,
) -> int:
    active_window = window or current_promise_window(now)
    if not active_window:
        logging.info("No promise window active at %s", now)
        print("[diagnostic] notify_weekend_promise: no active window")
        return 0

    label, rule = active_window
    print(f"[diagnostic] notify_weekend_promise: window={label} rule={rule}")
    nights = select_promising_nights(scored_days, now, rule)
    if not nights:
        logging.info("No promising nights for %s in %s window", city, label)
        print("[diagnostic] notify_weekend_promise: no nights met criteria")
        return 0

    print(f"[diagnostic] notify_weekend_promise: nights_selected={len(nights)}")
    message = build_promise_message(city, rule["label"], nights)
    print(f"[diagnostic] notify_weekend_promise: sending message='{message}'")
    notifs.send_push_notification(user_key, message, user_name=user_name)
    logging.info("Sent %s notification to %s: %s", label, user_name, message)
    return len(nights)


def main():
    now = get_adelaide_now()
    print(f"[diagnostic] main: start run_time={now.isoformat()}")
    window = current_promise_window(now)
    window_label = window[0] if window else None
    print(f"[diagnostic] main: window_label={window_label}")

    for name, user_key in config.USERS.items():
        for city, coords in config.LOCATIONS.items():
            lat, lon = [float(x) for x in coords.split(",")]
            print(f"[diagnostic] main: processing user={name} city={city} lat={lat} lon={lon}")
            scored = build_and_score(lat, lon, days=7)
            append_forecast_history(city, now.isoformat(), scored, window_label)
            notify_weekend_promise(scored, city, name, user_key, now, window)


if __name__ == "__main__":
    main()
