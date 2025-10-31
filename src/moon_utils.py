# src/moon_utils.py
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from astral import moon, LocationInfo
from astral.sun import sun
import math

def get_moon_sun_times(lat, lon, day, tz="Australia/Adelaide"):
    tzinfo = ZoneInfo(tz)
    loc = LocationInfo(latitude=lat, longitude=lon, timezone=tz)
    obs = loc.observer

    def fmt(dt):
        return dt.astimezone(tzinfo).strftime("%I:%M %p") if dt else None

    s_today = sun(obs, date=day, tzinfo=tzinfo)

    # 👇 tolerate polar-ish edge cases
    try:
        mr = moon.moonrise(obs, date=day, tzinfo=tzinfo)
    except ValueError:
        mr = None
    try:
        ms = moon.moonset(obs, date=day, tzinfo=tzinfo)
    except ValueError:
        ms = None

    age_days = moon.phase(day)  # 0=new … ~14.77=full
    phase_angle = 2 * math.pi * (age_days / 29.530588853)
    illum_pct = round(((1 - math.cos(phase_angle)) / 2) * 100, 1)

    return {
        "sunrise": fmt(s_today.get("sunrise")),
        "sunset":  fmt(s_today.get("sunset")),
        "moonrise": fmt(mr),
        "moonset":  fmt(ms),
        "illumination": illum_pct,
    }