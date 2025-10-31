from __future__ import print_function
from datetime import datetime, timedelta
import requests, json, config, numpy as np

# simple run-time status banner
def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

### weather api - utility functions
def send_api_request(url):
    """Sends an API request and returns JSON or error dict."""
    try:
        r = requests.get(url)
        if r.status_code == 200:
            log(f"api request ok ({len(r.text)} bytes)")
            return r.json()
        else:
            log(f"api request failed code={r.status_code}")
            return {"error": f"status {r.status_code}"}
    except requests.exceptions.RequestException as e:
        log(f"api request exception: {e}")
        return {"error": str(e)}

def validate_days(days):
    """Ensures days is an integer string between 1 and 10 inclusive."""
    if not days.isdigit():
        raise ValueError(f"Days '{days}' must be numeric")
    d = int(days)
    if not 1 <= d <= 10:
        raise ValueError(f"Days '{days}' out of range 1–10")

def get_forecast(location, days, aqi="no", alerts="no"):
    """Retrieves weather forecast data from Weather API."""
    validate_days(days)
    base_url = "http://api.weatherapi.com/v1/forecast.json"
    api_key = config.WEATHER_API_KEY
    url = f"{base_url}?key={api_key}&q={location}&days={days}&aqi={aqi}&alerts={alerts}"
    log(f"requesting forecast {location} for {days} days")
    return send_api_request(url)

def process_weather_data(weather_data, days_from_today=None):
    """Processes raw weather data into a structured daily summary."""

    def parse_astro_times(date, astro):
        """Parses sunset, moonrise, and moonset times."""
        def try_parse(label):
            t = astro.get(label)
            if not t or "No" in str(t):
                return None
            for fmt in ["%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                try:
                    return datetime.strptime(f"{date} {t}", fmt)
                except ValueError:
                    pass
            return None

        sunset_time = try_parse("sunset")
        moonrise_time = try_parse("moonrise")
        moonset_time = try_parse("moonset")
        if moonrise_time and moonset_time and moonset_time < moonrise_time:
            moonset_time += timedelta(days=1)
        return sunset_time, moonrise_time, moonset_time

    results = []
    mins_per_hour = 60
    log("processing weather data...")

    try:
        for daily_forecast in weather_data["forecast"]["forecastday"]:
            astro = daily_forecast["astro"]
            day = daily_forecast["day"]
            date = daily_forecast["date"]
            mintemp_c = day["mintemp_c"]
            sunset_time, moonrise_time, moonset_time = parse_astro_times(date, astro)
            if sunset_time is None:
                log(f"warning: no sunset time for {date}")
                continue

            rounded_time = (sunset_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            hour_data = {h["time"]: h for h in daily_forecast["hour"]}
            temp_time_str = rounded_time.strftime("%Y-%m-%d %H:%M")

            if temp_time_str not in hour_data:
                log(f"{date}: no hourly match near sunset, skipping")
                continue

            selected_hour = hour_data[temp_time_str]
            temp_c = selected_hour["temp_c"]
            if mintemp_c is None or selected_hour["dewpoint_c"] is None:
                dewpoint_risk = 0.0
            else:
                dewpoint_risk = selected_hour["dewpoint_c"] - mintemp_c
            wind_speed_kph = selected_hour["wind_kph"]
            humidity = selected_hour["humidity"]
            visibility_km = selected_hour["vis_km"]

            cloud_vals, dew_vals = [], []
            total_visible_minutes = 0

            for i in range(5):
                hour = rounded_time + timedelta(hours=i)
                key = hour.strftime("%Y-%m-%d %H:%M")
                if key not in hour_data:
                    continue
                h = hour_data[key]
                cloud_vals.append(h["cloud"])
                dew_vals.append(h["dewpoint_c"])
                if moonrise_time or moonset_time:
                    start, end = hour, hour + timedelta(hours=1)
                    if moonrise_time and moonset_time:
                        if moonrise_time < end and moonset_time > start:
                            visible_start = max(moonrise_time, start)
                            visible_end = min(moonset_time, end)
                            total_visible_minutes += (visible_end - visible_start).total_seconds() / 60
                    elif moonrise_time and not moonset_time and moonrise_time < end:
                        total_visible_minutes += (end - moonrise_time).total_seconds() / 60
                    elif not moonrise_time and moonset_time and moonset_time > start:
                        total_visible_minutes += (moonset_time - start).total_seconds() / 60

            if cloud_vals:
                avg_cloud, min_cloud, max_cloud = (
                    sum(cloud_vals) / len(cloud_vals),
                    min(cloud_vals),
                    max(cloud_vals),
                )
            else:
                avg_cloud = min_cloud = max_cloud = None

            if dew_vals:
                avg_dewpoint = sum(dew_vals) / len(dew_vals)
                min_dewpoint = min(dew_vals)
            else:
                avg_dewpoint = min_dewpoint = None

            moon_presence_percent = (total_visible_minutes / (5 * mins_per_hour)) * 100
            moon_illum = astro.get("moon_illumination")

            results.append({
                "date": date,
                "sunset": astro["sunset"],
                "moonrise": astro["moonrise"],
                "moonset": astro["moonset"],
                "moon_illumination": moon_illum,
                "temp_c": temp_c,
                "mintemp_c": mintemp_c,
                "avg_dewpoint": avg_dewpoint,
                "min_dewpoint": min_dewpoint,
                "dewpoint_risk": dewpoint_risk,
                "wind_speed_kph": wind_speed_kph,
                "humidity": humidity,
                "visibility_km": visibility_km,
                "avg_cloud": avg_cloud,
                "min_cloud": min_cloud,
                "max_cloud": max_cloud,
                "moon_presence": moon_presence_percent,
            })

            # print summary per day
            safe_avg = avg_cloud if avg_cloud is not None else 0
            log(f"{date}: avg_cloud={safe_avg:.1f}  moon={moon_presence_percent:.1f}% "
                f"illum={moon_illum}  wind={wind_speed_kph}  hum={humidity}")


    except KeyError as e:
        log(f"key error in data: {e}")
        return {"error": f"Missing {e}"}

    if days_from_today is not None:
        validate_days(days_from_today)
        return results[int(days_from_today) - 1]

    return results

def calculate_suitability_data(processed_data):
    """Models suitability scores for each condition."""

    def log_function(x, A, B, k, x0, condition=None):
        inside = k * (x - x0)
        if inside <= 0:
            return 0
        return A * np.log(inside) + B

    def logistic_function(x, L, k, x0, condition=None):
        output = L / (1 + pow(2.71828, -k * (x - x0)))
        if output > 100:
            output = 100
        limits = {1: 30, 2: 50, 3: 40, 4: 40, 5: 6}
        if condition in limits and x >= limits[condition]:
            return 0
        return output

    s = {
        "date": processed_data["date"],
        "avg_cloud": logistic_function(processed_data["avg_cloud"], **config.SUITABILITY_PARAMS["cloud"], condition=1),
        "min_cloud": logistic_function(processed_data["min_cloud"], **config.SUITABILITY_PARAMS["cloud"], condition=1),
        "max_cloud": logistic_function(processed_data["max_cloud"], **config.SUITABILITY_PARAMS["cloud"], condition=1),
        "moon_presence": logistic_function(processed_data["moon_presence"], **config.SUITABILITY_PARAMS["moon_presence"], condition=2),
        "moon_illumination": logistic_function(processed_data["moon_illumination"], **config.SUITABILITY_PARAMS["moon_presence"], condition=3),
        "wind_speed": logistic_function(processed_data["wind_speed_kph"], **config.SUITABILITY_PARAMS["wind_speed"], condition=4),
        "humidity": logistic_function(processed_data["humidity"], **config.SUITABILITY_PARAMS["humidity"]),
        "visibility": log_function(processed_data["visibility_km"], **config.SUITABILITY_PARAMS["visibility"]),
        "dewpoint_risk": logistic_function(processed_data["dewpoint_risk"], **config.SUITABILITY_PARAMS["dewpoint_risk"], condition=5),
    }

    # multiline readability log
    log(f"{s['date']}: component suitability:")
    for k, v in s.items():
        if k != "date":
            raw = processed_data.get(k + "_kph", processed_data.get(k, None))
            log(f"    {k:17s}: {v:6.1f}  ({raw})")

    return s

def get_suitability(s):
    """Combines weighted scores."""
    total = sum(s[c]*config.WEIGHTS[c] for c in s if c in config.WEIGHTS)
    log(f"{s['date']}: total suitability={total:.1f}")
    return total

def add_suitability_scores(processed_data):
    """Adds total suitability to daily results."""
    threshold = getattr(config, "NOTIFY_THRESHOLD", 60.0)
    for d in processed_data:
        s = calculate_suitability_data(d)
        total = get_suitability(s)
        d["suitability_score"] = total
        tag = "**GOOD**" if total >= threshold else "**REJECTED**"
        log(f"{tag} {d['date']}: {total:.1f}")
    return processed_data

# notification and json writer left mostly unchanged (they print concise final info)
def get_notification(results):
    """Generates a summary notification for high-suitability weekend days."""
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    good=[]
    for d in results:
        dow = datetime.strptime(d["date"],"%Y-%m-%d").weekday()
        if dow in (4,5) and d["suitability_score"]>=70:
            good.append(f"{days[dow]}: {d['suitability_score']:.1f}%")
    msg = "no good days upcoming" if not good else "  ".join(good)
    log("notification summary: " + msg)
    return msg

def write_json_to_file(data, filepath=None):
    """Writes data to disk."""
    if not filepath:
        s=datetime.strptime(data[0]['date'],'%Y-%m-%d').date()
        e=datetime.strptime(data[-1]['date'],'%Y-%m-%d').date()
        filepath=f"output_data/results_{s}_to_{e}.json"
    with open(filepath,"w") as f: json.dump(data,f,indent=4)
    log(f"wrote {len(data)} days to {filepath}")
