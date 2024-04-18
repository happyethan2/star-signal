import requests
import json
import swagger_client
import config

from __future__ import print_function
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint
import json
from datetime import datetime, timedelta

from datetime import datetime, timedelta
import config

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





def get_forecast(lat, lon, date):
    base_url = "http://api.weatherapi.com/v1/future.json"
    api_key = config.WEATHER_API_KEY
    url = f"{base_url}?key={api_key}&q={lat},{lon}&dt={date}"
    return send_api_request(url)

# Load the provided JSON data
with open('/mnt/data/example_forecast.json', 'r') as file:
    weather_data = json.load(file)


# Define the function to process the weather data as previously discussed
def process_weather_data(weather_data):
    try:
        forecast = weather_data['forecast']['forecastday'][0]
        astro = forecast['astro']
        sunset = astro['sunset']
        sunset_time = datetime.strptime(f"{forecast['date']} {sunset}", "%Y-%m-%d %I:%M %p")
        rounded_time = (sunset_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        temp_time_str = rounded_time.strftime("%Y-%m-%d %H:%M")
        hour_data = {item['time']: item for item in forecast['hour']}
        temp_c = hour_data[temp_time_str]['temp_c']
        dewpoint_c = hour_data[temp_time_str]['dewpoint_c']

        # Calculate cloud cover data
        cloud_values = []
        for i in range(5):
            hour = rounded_time + timedelta(hours=i)
            if hour.strftime("%Y-%m-%d %H:%M") in hour_data:
                cloud_values.append(hour_data[hour.strftime("%Y-%m-%d %H:%M")]['cloud'])

        if cloud_values:
            avg_cloud = sum(cloud_values) / len(cloud_values)
            cloud_range = f"{min(cloud_values)}-{max(cloud_values)}"
        else:
            avg_cloud, cloud_range = None, None

        return {
            "sunset": sunset,
            "moonrise": astro['moonrise'],
            "moonset": astro['moonset'],
            "moon_illumination": astro['moon_illumination'],
            "temp_c": temp_c,
            "dewpoint_c": dewpoint_c,
            "avg_cloud": avg_cloud,
            "cloud_range": cloud_range
        }
    except KeyError as e:
        return {"error": f"Key error: Missing data {str(e)}"}

# Test the function with the provided data
processed_data = process_weather_data(weather_data)
processed_data