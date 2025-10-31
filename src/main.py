import logging
import sys
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# --- import path setup (keep identical) ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- local imports (identical) ---
import config  # noqa: E402
from src import pushover_utils as notifs  # noqa: E402
from src import utils  # noqa: E402
from src.data_store import append_forecast_history  # noqa: E402
from src.provider_vc import fetch_visualcrossing  # noqa: E402

# --- logging configuration (unchanged: still writes to output.log) ---
logging.basicConfig(
    filename="output.log",
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
)

# --- constants / simple config ---
ADEL_TZ = ZoneInfo("Australia/Adelaide")
WEEKEND_TARGETS = (4, 5, 6)  # 4=Fri, 5=Sat, 6=Sun

# notification windows by weekday/time with min score requirement
PROMISE_WINDOWS: Dict[str, Dict[str, object]] = {
    "sunday":    {"weekday": 6, "start": time(17, 0), "score_min": 0.0,  "label": "weekend outlook"},
    "wednesday": {"weekday": 2, "start": time(17, 0), "score_min": 60.0, "label": "mid-week update"},
    "thursday":  {"weekday": 3, "start": time(17, 0), "score_min": 65.0, "label": "thursday confidence"},
    "friday":    {"weekday": 4, "start": time(17, 0), "score_min": 70.0, "label": "final go/no-go"},
}


def build_and_score(lat: float, lon: float, days: int = 7) -> List[dict]:
    """fetch forecast, compute features, add suitability scores"""
    print(f"[diagnostic] build_and_score: lat={lat} lon={lon} days={days}")
    data = fetch_visualcrossing(lat, lon, days=days)
    logging.info("Fetched data for lat=%.4f lon=%.4f days=%d", lat, lon, days)

    processed = utils.process_weather_data(data)
    scored = utils.add_suitability_scores(processed)

    print(f"[diagnostic] build_and_score: scored_count={len(scored)}")
    return scored


def get_adelaide_now() -> datetime:
    """current time in Adelaide tz"""
    return datetime.now(tz=ADEL_TZ)


def _weekday_name(i: int) -> str:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i % 7]


def _list_valid_windows() -> str:
    # simple readable summary of configured run windows
    items = []
    for key, rule in PROMISE_WINDOWS.items():
        items.append(f"{key} (weekday={_weekday_name(rule['weekday'])}, start={rule['start'].strftime('%H:%M')}, min={rule['score_min']:.0f})")
    return "; ".join(items)


def current_promise_window(now: datetime) -> Optional[Tuple[str, Dict[str, object]]]:
    """return (label, window) if a promise window is active at 'now'"""
    print(f"[diagnostic] current_promise_window: now={now.isoformat()}")

    for label, rule in PROMISE_WINDOWS.items():
        if now.weekday() == rule["weekday"] and now.time() >= rule["start"]:
            print(f"[diagnostic] current_promise_window: matched={label} threshold={rule.get('score_min')}")
            return label, rule

    # explicit note when not a valid day/time to notify
    print(
        "[diagnostic] current_promise_window: no active window — "
        f"today={_weekday_name(now.weekday())} time={now.strftime('%H:%M')}. "
        f"valid run windows: { _list_valid_windows() }"
    )
    return None


def upcoming_weekend_dates(reference: datetime) -> List[datetime.date]:
    """
    return list of dates for Fri/Sat/Sun relative to 'reference'.
    if run on Sunday (weekday==6) it also includes the next Sunday.
    """
    targets: List[datetime.date] = []

    for target_wd in WEEKEND_TARGETS:
        base_offset = (target_wd - reference.weekday()) % 7
        offsets = [base_offset]

        # special case: on sunday, include next sunday too
        if base_offset == 0 and reference.weekday() == 6 and target_wd == 6:
            offsets.append(7)

        for off in offsets:
            d = (reference + timedelta(days=off)).date()
            if d not in targets:
                targets.append(d)

    return targets


def _safe_float(value, default: float) -> float:
    """coerce value to float or return default"""
    try:
        if value is None:
            raise ValueError("None value")
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def select_promising_nights(scored_days: List[dict], reference: datetime, rule: Dict[str, object]) -> Tuple[List[dict], List[dict]]:
    """
    choose weekend dates meeting rule['score_min']; keep raw record for message.
    also return a per-date decision log for diagnostics.
    """
    print(f"[diagnostic] select_promising_nights: reference={reference.date()} score_min={rule.get('score_min')}")
    by_date = {datetime.strptime(d["date"], "%Y-%m-%d").date(): d for d in scored_days if "date" in d}

    score_min = float(rule.get("score_min", 85.0))
    weekend_dates = upcoming_weekend_dates(reference)

    selections: List[dict] = []
    decisions: List[dict] = []  # [{date, status, reason, score?}]

    for target in weekend_dates:
        record = by_date.get(target)

        if not record:
            decisions.append({"date": target, "status": "not_notified", "reason": "no_forecast_data"})
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
            decisions.append({
                "date": target,
                "status": "not_notified",
                "reason": f"below_threshold({score:.1f} < {score_min:.1f})",
                "score": score,
            })
            logging.info("Rejecting %s (score %.1f below %.1f)", record.get("date"), score, score_min)
            print(f"[diagnostic] select_promising_nights: rejected below threshold for {record.get('date')}")
            continue

        # eligible (will be notified later if we send a message)
        selections.append({
            "date": target,
            "score": score,
            "avg_cloud": _safe_float(avg_cloud, 0.0),
            "raw": record,
        })
        decisions.append({
            "date": target,
            "status": "eligible",
            "reason": "meets_threshold",
            "score": score,
        })

    print(f"[diagnostic] select_promising_nights: selections={len(selections)}")
    # summary for all considered targets
    for d in decisions:
        tag = "ELIGIBLE" if d["status"] == "eligible" else "NOT_NOTIFIED"
        extra = f" score={d.get('score'):.1f}" if "score" in d else ""
        print(f"[diagnostic] considered {d['date']}: {tag} ({d['reason']}){extra}")

    return sorted(selections, key=lambda item: item["date"]), decisions


def build_promise_message(city: str, rule_label: str, nights: List[dict]) -> str:
    """render concise message like 'Adelaide final go/no-go: Fri 01 72% (cloud 21%) | ...'"""
    parts: List[str] = []
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
    """
    send a push if an active window exists and qualifying nights are found.
    prints explicit diagnostics for:
      - running outside a valid window
      - each considered date (eligible vs not_notified)
      - which dates were actually notified
    """
    active = window or current_promise_window(now)

    if not active:
        logging.info("No promise window active at %s", now)
        print(
            "[diagnostic] notify_weekend_promise: no active window — "
            f"today={_weekday_name(now.weekday())} time={now.strftime('%H:%M')}.\n"
            f"[diagnostic] valid run windows: { _list_valid_windows() }"
        )
        return 0

    label, rule = active
    print(f"[diagnostic] notify_weekend_promise: window={label} rule={rule}")

    nights, decisions = select_promising_nights(scored_days, now, rule)
    if not nights:
        logging.info("No promising nights for %s in %s window", city, label)
        print("[diagnostic] notify_weekend_promise: no nights met criteria (nothing sent)")
        return 0

    print(f"[diagnostic] notify_weekend_promise: nights_selected={len(nights)}")
    message = build_promise_message(city, rule["label"], nights)
    print(f"[diagnostic] notify_weekend_promise: sending message='{message}'")

    notifs.send_push_notification(user_key, message, user_name=user_name)
    logging.info("Sent %s notification to %s: %s", label, user_name, message)

    # print exactly which dates were notified (eligible list)
    for night in nights:
        print(f"[diagnostic] notified for {night['date']}: score={night['score']:.1f}")

    # and also re-state which considered dates did NOT get notified (from decisions)
    for d in decisions:
        if d["status"] != "eligible":
            print(f"[diagnostic] not notified for {d['date']}: {d['reason']}")

    return len(nights)


def main():
    """main orchestration: detect window, process each user/city, record+notify"""
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
