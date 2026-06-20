"""
One-shot live test: fetches real Adelaide weather, scores it, and sends a
Pushover notification so you can verify format and delivery on your phone.

Run with:  python test_notify.py
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from src.provider_vc import fetch_visualcrossing
from src import utils
from src import pushover_utils as notifs
from src.main import upcoming_weekend_dates, ADEL_TZ
from src.message_builder import generate_notification_message

now = datetime.now(tz=ADEL_TZ)
lat, lon = [float(x) for x in config.LOCATIONS["Adelaide"].split(",")]

print(f"[test] current Adelaide time : {now.strftime('%A %Y-%m-%d %H:%M %Z')}")
print(f"[test] fetching live forecast for ({lat}, {lon}) ...")

data = fetch_visualcrossing(lat, lon, days=7)
processed = utils.process_weather_data(data)
scored = utils.add_suitability_scores(processed)

target_dates = upcoming_weekend_dates(now)
by_date = {datetime.strptime(d["date"], "%Y-%m-%d").date(): d for d in scored if "date" in d}

nights = []
for target in sorted(target_dates):
    record = by_date.get(target)
    if record:
        nights.append({
            "date": target,
            "score": record["suitability_score"],
            "avg_cloud": record.get("avg_cloud", 0.0),
            "raw": record,
        })
    else:
        print(f"[test] WARNING: no forecast data for {target}")

if not nights:
    print("[test] No matching forecast dates — cannot send notification.")
    sys.exit(1)

print(f"\n[test] Upcoming weekend dates targeted: {[str(d) for d in target_dates]}")
for n in nights:
    print(f"[test]   {n['date']} ({n['date'].strftime('%A')})  score={n['score']:.1f}  cloud={n['avg_cloud']:.1f}%")

threshold = config.NOTIFY_THRESHOLD if hasattr(config, "NOTIFY_THRESHOLD") else 60.0
message = generate_notification_message("Adelaide", "weekend outlook", nights, threshold=threshold)
print(f"\n[test] Notification message:\n       {message}\n")

for name, user_key in config.USERS.items():
    notifs.send_push_notification(user_key, message, user_name=name)
    print(f"[test] Sent to {name}")
