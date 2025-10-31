import os
import json
import requests
from datetime import datetime
from src.moon_utils import get_moon_sun_times

import logging
logger = logging.getLogger("star_signal")


OFFLINE_TESTING = True

try:
    import config as _root_cfg  # when run from src/ as a script
    if hasattr(_root_cfg, "OFFLINE_TESTING"):
        OFFLINE_TESTING = bool(_root_cfg.OFFLINE_TESTING)
except Exception:
    try:
        from src import config as _pkg_cfg  # when run as a package
        if hasattr(_pkg_cfg, "OFFLINE_TESTING"):
            OFFLINE_TESTING = bool(_pkg_cfg.OFFLINE_TESTING)
    except Exception:
        pass


def _vc_to_weatherapi_like(vc_json, lat=None, lon=None):
    forecastday = []
    for day in vc_json.get("days", []):
        date = day.get("datetime")

        # Always compute with Astral (uses local timezone inside helper)
        astro_calc = get_moon_sun_times(
            lat, lon, datetime.strptime(date, "%Y-%m-%d").date()
        )
        astro = {
            "sunrise": astro_calc["sunrise"],
            "sunset": astro_calc["sunset"],
            "moonrise": astro_calc["moonrise"],
            "moonset": astro_calc["moonset"],
            "moon_illumination": astro_calc["illumination"],
        }

        hours = []
        for h in day.get("hours", []) or []:
            timestr = f"{date} {str(h.get('datetime','00:00:00'))[:5]}"
            hours.append({
                "time": timestr,
                "temp_c": h.get("temp"),
                "dewpoint_c": h.get("dew"),
                "wind_kph": h.get("windspeed"),
                "humidity": h.get("humidity"),
                "vis_km": h.get("visibility"),
                "cloud": h.get("cloudcover"),
            })

        daily = {
            "date": date,
            "day": {"mintemp_c": day.get("tempmin"), "maxtemp_c": day.get("tempmax", None)},
            "astro": astro,
            "hour": hours,
        }
        forecastday.append(daily)
    return {"forecast": {"forecastday": forecastday}}


def _load_offline(path, lat, lon):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    days_ct = len((data if not OFFLINE_TESTING else data).get("days", []))
    logger.info("[provider] raw_days=%d elements=request(datetime,temp,humidity,dew,windspeed,visibility,cloudcover,moonphase)+astral(sun/moon)", days_ct)

    return _vc_to_weatherapi_like(data, lat, lon)


def fetch_visualcrossing(lat, lon, days=7):
    mode = "OFFLINE" if OFFLINE_TESTING else "ONLINE"
    logger.info("[provider] mode=%s lat=%.4f lon=%.4f days=%d", mode, lat, lon, days)

    if OFFLINE_TESTING:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        test_path = os.path.join(data_dir, "test.json")
        logging.info("OFFLINE mode: loading %s", test_path)

        return _load_offline(test_path, lat, lon)

    # online path (not used while testing)
    try:
        try:
            from src import config as cfg
        except Exception:
            import config as cfg

        key = getattr(cfg, "VISUAL_CROSSING_API_KEY", "")
        if not key:
            raise RuntimeError("VISUAL_CROSSING_API_KEY missing in config")

        
        base = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        url = f"{base}/{lat},{lon}"
        params = {
            "unitGroup": "metric",
            "include": "hours",
            "key": key,
            "elements": "datetime,temp,humidity,dew,windspeed,visibility,cloudcover,moonphase",
            "forecastDays": str(days)
        }

        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        vc_json = r.json()
        logging.info("Online VC fetch ok: %d days", len(vc_json.get("days", [])))

        days_ct = len((vc_json if not OFFLINE_TESTING else vc_json).get("days", []))
        logger.info("[provider] raw_days=%d elements=request(datetime,temp,humidity,dew,windspeed,visibility,cloudcover,moonphase)+astral(sun/moon)", days_ct)

        return _vc_to_weatherapi_like(vc_json, -34.9285, 138.6007)
    
    except Exception as e:
        logging.error("Visual Crossing fetch failed: %s", e)
        raise
