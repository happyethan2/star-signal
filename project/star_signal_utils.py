from __future__ import print_function
from datetime import datetime, timedelta

import requests
import json
import config
import swagger_client


### RapidAPI - Utility Functions
def get_moon_phase(lat, lon):
    url = "https://moon-phase.p.rapidapi.com/advanced"

    querystring = {"lat": lat,"lon": lon}

    headers = {
        "X-RapidAPI-Key": "6c925f5fc2msh9b0d7fdec48e8a5p1e3e99jsndb79e168c058",
        "X-RapidAPI-Host": "moon-phase.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    response = json.dumps(response.json(), indent=4)

    return response


### Weather API - Utility Functions
def send_api_request(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to retrieve data: Status code {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def validate_days(days):
    if not days.isdigit():
        raise ValueError(f"Days '{days}' must be a string representation of an integer")
    try:
        days_int = int(days)  # Attempt to convert to integer
        if not 1 <= days_int <= 10:  # Check if it's between 1 and 10
            raise ValueError(f"Days '{days}' must be an integer between 1 and 10 inclusive")
    except ValueError:
        # This will catch cases where conversion to integer fails
        raise ValueError(f"Days '{days}' must be a valid integer between 1 and 10 inclusive")
    

def get_forecast(location, days, aqi='no', alerts='no'):
    validate_days(days)

    base_url = "http://api.weatherapi.com/v1/forecast.json"
    api_key = config.WEATHER_API_KEY
    url = f"{base_url}?key={api_key}&q={location}&days={days}&aqi={aqi}&alerts={alerts}"
    return send_api_request(url)


# Define the function to process the weather data as previously discussed
def process_weather_data(weather_data, day=None):
    results = []
    try:
        for daily_forecast in weather_data['forecast']['forecastday']:
            astro = daily_forecast['astro']
            sunset = astro['sunset']
            date = daily_forecast['date']
            sunset_time = datetime.strptime(f"{date} {sunset}", "%Y-%m-%d %I:%M %p")
            rounded_time = (sunset_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            temp_time_str = rounded_time.strftime("%Y-%m-%d %H:%M")
            hour_data = {item['time']: item for item in daily_forecast['hour']}
            if temp_time_str in hour_data:
                temp_c = hour_data[temp_time_str]['temp_c']
                dewpoint_c = hour_data[temp_time_str]['dewpoint_c']
                # Calculate cloud cover data for 5 hours post-sunset
                cloud_values = []
                for i in range(5):
                    hour = rounded_time + timedelta(hours=i)
                    hour_str = hour.strftime("%Y-%m-%d %H:%M")
                    if hour_str in hour_data:
                        cloud_values.append(hour_data[hour_str]['cloud'])

                if cloud_values:
                    avg_cloud = sum(cloud_values) / len(cloud_values)
                    cloud_range = f"{min(cloud_values)}-{max(cloud_values)}"
                else:
                    avg_cloud, cloud_range = None, None

                results.append({
                    "date": date,
                    "sunset": sunset,
                    "moonrise": astro['moonrise'],
                    "moonset": astro['moonset'],
                    "moon_illumination": astro['moon_illumination'],
                    "temp_c": temp_c,
                    "dewpoint_c": dewpoint_c,
                    "avg_cloud": avg_cloud,
                    "cloud_range": cloud_range
                })
    except KeyError as e:
        return {"error": f"Key error: Missing data {str(e)}"}

    if day is not None:
        validate_days(day)
        return results[int(day) - 1]

    return results