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

    sys.modules["requests"] = SimpleNamespace(
        get=lambda *a, **kw: _FakeResponse(),
        post=lambda *a, **kw: _FakeResponse(),
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
            "sunset":  datetime.combine(date, time(19, 30), tzinfo),
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
    """Build a scored dataset covering the 3 weekend nights from reference."""
    dataset = []
    for target in main.upcoming_weekend_dates(reference):
        dataset.append({
            "date": target.strftime("%Y-%m-%d"),
            "suitability_score": score,
            "avg_cloud": avg_cloud,
            "min_cloud": avg_cloud,
            "max_cloud": avg_cloud,
            "moon_presence": moon_presence,
            "moon_illumination": 0.0,
            "sunset": "07:30 PM",
            "moonrise": "08:00 PM",
            "moonset": "05:00 AM",
            "wind_speed_kph": 10.0,
            "humidity": 40.0,
            "visibility_km": 10.0,
            "dewpoint_risk": 1.0,
        })
    return dataset


class PromiseNotificationHarness(unittest.TestCase):
    def setUp(self):
        self.notifications = []
        self.append_calls = []

        self.original_send = main.notifs.send_push_notification
        self.original_append = main.append_forecast_history
        self.original_monday_check = main.monday_notified_this_week

        from src import data_store
        self.data_store = data_store
        self.original_append_module = data_store.append_forecast_history

        # default: Monday was NOT notified (tests that need it set self._monday_notified = True)
        self._monday_notified = False

        def fake_send(user_key, message, user_name="user"):
            self.notifications.append({"user": user_name, "key": user_key, "message": message})
            print(f"  -> Notification to {user_name}: {message}")

        def fake_append(city, run_timestamp_iso, scored_days, promise_window):
            self.append_calls.append({
                "city": city,
                "timestamp": run_timestamp_iso,
                "promise_window": promise_window,
                "count": len(scored_days),
            })

        def fake_monday_check(city, now):
            return self._monday_notified

        def fake_generate_message(city, rule_label, nights, threshold=60.0):
            _abbrev = {4: "Fri", 5: "Sat", 6: "Sun"}
            parts = [_abbrev.get(n["date"].weekday(), n["date"].strftime("%a")) for n in nights]
            return f"{city} {rule_label} — {' · '.join(parts)}"

        self.original_generate_message = main.generate_notification_message
        main.generate_notification_message = fake_generate_message

        main.notifs.send_push_notification = fake_send
        main.append_forecast_history = fake_append
        data_store.append_forecast_history = fake_append
        main.monday_notified_this_week = fake_monday_check

    def tearDown(self):
        main.notifs.send_push_notification = self.original_send
        main.append_forecast_history = self.original_append
        main.monday_notified_this_week = self.original_monday_check
        main.generate_notification_message = self.original_generate_message
        self.data_store.append_forecast_history = self.original_append_module

    def run_scenario(self, label, now, scored_days, expected_nights, expect_messages=None):
        self.notifications.clear()
        self.append_calls.clear()

        print(f"\n=== Scenario: {label} ===")
        print(f"Reference time (Adelaide): {now.isoformat()}")
        for day in scored_days:
            print(
                f"  Candidate {day['date']}: score={day['suitability_score']} "
                f"cloud={day['avg_cloud']} moon={day['moon_presence']}"
            )

        main.append_forecast_history("Adelaide", now.isoformat(), scored_days, None)
        count = main.notify_weekend_promise(scored_days, "Adelaide", "Ethan", "dummy-user", now)

        if not self.notifications:
            print("  Notifications dispatched: none")
        print(f"  Result: {count} night(s) notified")
        print(f"=== End: {label} ===\n")

        if expect_messages is None:
            expect_messages = 1 if expected_nights > 0 else 0

        self.assertEqual(count, expected_nights)
        self.assertEqual(len(self.notifications), expect_messages)
        return self.notifications

    # --- schedule window tests ---

    def test_monday_always_sends_all_three_nights(self):
        """Monday 19:30 triggers the outlook regardless of scores; all 3 weekend nights included."""
        run_time = datetime(2025, 2, 17, 19, 30, tzinfo=main.ADEL_TZ)  # Monday
        scored_days = build_weekend_dataset(run_time, score=65.0, avg_cloud=20.0)
        notes = self.run_scenario("Monday outlook", run_time, scored_days, 3)
        self.assertIn("weekend outlook", notes[0]["message"])
        self.assertIn("Fri", notes[0]["message"])
        self.assertIn("Sat", notes[0]["message"])
        self.assertIn("Sun", notes[0]["message"])

    def test_monday_sends_even_with_low_scores(self):
        """Monday window has score_min=0 — sends even when all nights look terrible."""
        run_time = datetime(2025, 2, 17, 19, 30, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=5.0, avg_cloud=90.0)
        notes = self.run_scenario("Monday outlook bad weather", run_time, scored_days, 3)
        self.assertEqual(len(notes), 1)

    def test_wednesday_sends_when_monday_was_notified(self):
        """Wednesday follow-up sends when Monday notification is on record for this week."""
        self._monday_notified = True
        run_time = datetime(2025, 2, 19, 19, 30, tzinfo=main.ADEL_TZ)  # Wednesday
        scored_days = build_weekend_dataset(run_time, score=78.0, avg_cloud=15.0)
        notes = self.run_scenario("Wednesday follow-up (Monday sent)", run_time, scored_days, 3)
        self.assertIn("updated forecast", notes[0]["message"])

    def test_wednesday_skips_when_monday_was_not_notified(self):
        """Wednesday follow-up is suppressed when no Monday notification exists this week."""
        self._monday_notified = False
        run_time = datetime(2025, 2, 19, 19, 30, tzinfo=main.ADEL_TZ)
        scored_days = build_weekend_dataset(run_time, score=78.0, avg_cloud=15.0)
        self.run_scenario("Wednesday follow-up (Monday not sent)", run_time, scored_days, 0)

    def test_outside_schedule_no_window(self):
        """Runs on Tuesday or any off-schedule time send nothing."""
        run_time = datetime(2025, 2, 18, 19, 30, tzinfo=main.ADEL_TZ)  # Tuesday
        scored_days = build_weekend_dataset(run_time, score=90.0, avg_cloud=5.0)
        self.run_scenario("Tuesday (outside schedule)", run_time, scored_days, 0)

    # --- date calculation tests ---

    def test_upcoming_weekend_dates_from_monday(self):
        """From Monday, upcoming_weekend_dates returns the Fri/Sat/Sun of that same week."""
        monday = datetime(2025, 2, 17, 10, 0, tzinfo=main.ADEL_TZ)
        dates = main.upcoming_weekend_dates(monday)
        self.assertEqual(len(dates), 3)
        weekdays = [d.weekday() for d in dates]
        self.assertIn(4, weekdays)  # Friday
        self.assertIn(5, weekdays)  # Saturday
        self.assertIn(6, weekdays)  # Sunday
        for d in dates:
            self.assertGreater(d, monday.date())  # never includes today

    def test_upcoming_weekend_dates_from_wednesday(self):
        """From Wednesday, upcoming_weekend_dates returns the same Fri/Sat/Sun."""
        wednesday = datetime(2025, 2, 19, 10, 0, tzinfo=main.ADEL_TZ)
        dates = main.upcoming_weekend_dates(wednesday)
        self.assertEqual(len(dates), 3)
        weekdays = [d.weekday() for d in dates]
        self.assertIn(4, weekdays)
        self.assertIn(5, weekdays)
        self.assertIn(6, weekdays)
        for d in dates:
            self.assertGreater(d, wednesday.date())


if __name__ == "__main__":
    unittest.main(verbosity=2)
