import config
from src import utils
from src import pushover_utils as notifs
import config

from src.provider_vc import fetch_visualcrossing
import logging

logging.basicConfig(
    filename='output.log',
    level=logging.INFO,
    format='%(asctime)s: %(levelname)s: %(message)s',
)

def build_and_score(lat, lon, days=7):
    data = fetch_visualcrossing(lat, lon, days=days)
    logging.info("Fetched data for lat=%.4f lon=%.4f days=%d", lat, lon, days)
    processed = utils.process_weather_data(data)
    scored = utils.add_suitability_scores(processed)
    return scored

def notify_if_good(scored_days, user_name, user_key, threshold_pct=None):
    import logging
    threshold = threshold_pct if threshold_pct is not None else getattr(config, "NOTIFY_THRESHOLD", 60.0)

    # keep only the days above threshold
    good = []
    for d in scored_days:
        try:
            score = float(d.get("suitability_score", 0))
        except (TypeError, ValueError):
            score = 0.0
        if score >= threshold:
            good.append((d.get("date", "?"), score))

    if not good:
        logging.info("No days exceed threshold %.1f for %s", threshold, user_name)
        return 0

    # concise message: date + score
    lines = [f"{dt}: {s:.1f}" for dt, s in sorted(good)]
    message = "Astrophotography conditions (≥{:.0f}):\n{}".format(threshold, "\n".join(lines))
    notifs.send_push_notification(user_key, message, user_name=user_name)
    return len(good)


def main():
    for name, user_key in config.USERS.items():
        for city, coords in config.LOCATIONS.items():
            lat, lon = [float(x) for x in coords.split(',')]
            scored = build_and_score(lat, lon, days=7)
            notify_if_good(scored, name, user_key, config.NOTIFY_THRESHOLD)

if __name__ == "__main__":
    main()