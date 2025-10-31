from __future__ import annotations

import sys
import unittest
from datetime import datetime, time, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace


if "requests" not in sys.modules:
    class _FakeResponse:
        def __init__(self, status_code=200, json_data=None, text="ok"):
            self.status_code = status_code
            self._json_data = json_data or {}
            self.text = text

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

    def _fake_get(*args, **kwargs):
        return _FakeResponse()

    def _fake_post(*args, **kwargs):
        return _FakeResponse()

    sys.modules["requests"] = SimpleNamespace(
        get=_fake_get,
        post=_fake_post,
        exceptions=SimpleNamespace(RequestException=Exception),
    )

if "astral" not in sys.modules:
    class _FakeLocationInfo:
        def __init__(self, latitude, longitude, timezone):
            self.latitude = latitude
            self.longitude = longitude
            self.timezone = timezone
            self.observer = SimpleNamespace(latitude=latitude, longitude=longitude, elevation=0)

    def _fake_moonrise(observer, date, tzinfo=None):
        return datetime.combine(date, time(20, 0), tzinfo)

    def _fake_moonset(observer, date, tzinfo=None):
        return datetime.combine(date + timedelta(days=1), time(5, 0), tzinfo)

    def _fake_phase(date):
        return 0.0

    def _fake_sun(observer, date, tzinfo=None):
        return {
            "sunrise": datetime.combine(date, time(6, 30), tzinfo),
            "sunset": datetime.combine(date, time(19, 30), tzinfo),
        }

    astral_module = ModuleType("astral")
    moon_module = ModuleType("astral.moon")
    sun_module = ModuleType("astral.sun")

    moon_module.moonrise = _fake_moonrise
    moon_module.moonset = _fake_moonset
    moon_module.phase = _fake_phase
    sun_module.sun = _fake_sun

    astral_module.moon = moon_module
    astral_module.LocationInfo = _FakeLocationInfo

    sys.modules["astral"] = astral_module
    sys.modules["astral.moon"] = moon_module
    sys.modules["astral.sun"] = sun_module


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import main


def build_weekend_dataset(reference: datetime, score: float, avg_cloud: float, moon_presence: float = 0.0):
    dataset = []
    for target in main.upcoming_weekend_dates(reference):
        dataset.append(
            {
                "date": target.strftime("%Y-%m-%d"),
                "suitability_score": score,
                "avg_cloud": avg_cloud,
                "min_cloud": avg_cloud,
                "max_cloud": avg_cloud,
                "moon_presence": moon_presence,
                "moon_illumination": 0.0,
                "sunset": "19:45 PM",
                "moonrise": "None",
                "moonset": "05:30 AM",
                "wind_speed_kph": 10.0,
                "humidity": 40.0,
                "visibility_km": 10.0,
                "dewpoint_risk": 1.0,
            }
        )
    return dataset


class PromiseNotificationHarness(unittest.TestCase):
    def setUp(self):
        self.notifications = []
        self.append_calls = []
        self.original_send = main.notifs.send_push_notification
        self.original_append = main.append_forecast_history

        from src import data_store

        self.data_store = data_store
        self.original_append_module = data_store.append_forecast_history

        def fake_send(user_key, message, user_name="user"):
            self.notifications.append({"user": user_name, "key": user_key, "message": message})
            print(f"  -> Notification to {user_name} ({user_key}): {message}")

        def fake_append(city, run_timestamp_iso, scored_days, promise_window):
            self.append_calls.append(
                {
                    "city": city,
                    "timestamp": run_timestamp_iso,
                    "promise_window": promise_window,
                    "count": len(scored_days),
                }
            )
            print(
                f"  -> Persisted {len(scored_days)} day(s) for {city} "
                f"(window={promise_window or 'none'}) at {run_timestamp_iso}"
            )

        main.notifs.send_push_notification = fake_send
        main.append_forecast_history = fake_append
        data_store.append_forecast_history = fake_append

    def tearDown(self):
        main.notifs.send_push_notification = self.original_send
        main.append_forecast_history = self.original_append
        self.data_store.append_forecast_history = self.original_append_module

    def run_scenario(self, label, now, scored_days, expected_nights, expect_messages=None):
        self.notifications.clear()
        self.append_calls.clear()

        print(f"\n=== Scenario: {label} ===")
        print(f"Reference time (Adelaide): {now.isoformat()}")
        for day in scored_days:
            print(
                f"Candidate {day['date']}: score={day['suitability_score']} "
                f"cloud={day['avg_cloud']} moon={day['moon_presence']}"
            )

        main.append_forecast_history("Adelaide", now.isoformat(), scored_days, None)
        count = main.notify_weekend_promise(scored_days, "Adelaide", "Ethan", "dummy-user", now)

        if not self.notifications:
            print("Notifications dispatched: none")
        print(f"Persist calls recorded: {len(self.append_calls)}")
        print(f"Scenario result: {count} notification(s)")
        print(f"=== End Scenario: {label} ===\n")

        if expect_messages is None:
            expect_messages = 1 if expected_nights > 0 else 0

        self.assertEqual(count, expected_nights)
        self.assertEqual(len(self.notifications), expect_messages)
        return self.notifications

    def test_sunday_outlook_triggers_notification(self):
        run_time = datetime(2025, 2, 16, 17, 30, tzinfo=main.ADEL_TZ)  # Sunday evening
        scored_days = build_weekend_dataset(run_time, score=58.0, avg_cloud=75.0)
        notes = self.run_scenario("Sunday weekend outlook (should notify)", run_time, scored_days, 2)
        self.assertIn("weekend outlook", notes[0]["message"])

    def test_wednesday_update_triggers_notification(self):
        run_time = datetime(2025, 2, 19, 18, 15, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=72.0, avg_cloud=55.0)
        if len(scored_days) > 1:
            scored_days[1]["avg_cloud"] = 75.0  # force Saturday to fail cloud threshold
        notes = self.run_scenario("Wednesday mid-week update (should notify)", run_time, scored_days, 1)
        self.assertIn("mid-week update", notes[0]["message"])

    def test_wednesday_rejects_due_to_cloud(self):
        run_time = datetime(2025, 2, 19, 19, 0, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=80.0, avg_cloud=75.0)
        self.run_scenario("Wednesday cloud limit (should skip)", run_time, scored_days, 0)

    def test_thursday_rejects_due_to_low_score(self):
        run_time = datetime(2025, 2, 20, 18, 15, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=60.0, avg_cloud=40.0)
        self.run_scenario("Thursday insufficient score (should skip)", run_time, scored_days, 0)

    def test_friday_final_go_notification(self):
        run_time = datetime(2025, 2, 21, 18, 10, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=82.0, avg_cloud=28.0)
        notes = self.run_scenario("Friday final go/no-go (should notify)", run_time, scored_days, 2)
        self.assertIn("final go/no-go", notes[0]["message"])

    def test_friday_rejects_due_to_moon_presence(self):
        run_time = datetime(2025, 2, 21, 18, 45, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=85.0, avg_cloud=25.0, moon_presence=15.0)
        self.run_scenario("Friday moon presence (should skip)", run_time, scored_days, 0)

    def test_outside_schedule_no_window(self):
        run_time = datetime(2025, 2, 18, 12, 0, tzinfo=main.ADEL_TZ)  # Tuesday midday
        scored_days = build_weekend_dataset(run_time, score=90.0, avg_cloud=20.0)
        self.run_scenario("Outside schedule (should skip)", run_time, scored_days, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
