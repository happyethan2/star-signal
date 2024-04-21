from __future__ import print_function
from datetime import datetime, timedelta

import requests
import json
import config
import swagger_client


### RapidAPI - Utility Functions
def get_moon_phase(lat, lon):
    """
    This function retrieves the moon phase data for a specified location using the Moon Phase API.

    Args:
        lat (str): Latitude of the location.
        lon (str): Longitude of the location.
    Returns:
        str: JSON response containing the moon phase data.
    """
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
    """
    This function sends an API request to the specified URL and returns the JSON response.
    If the request fails, an error message is returned instead.

    Args:
        url (str): URL for the API request.
    Returns:
        dict: JSON response from the API request or an error message.
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to retrieve data: Status code {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def validate_days(days):
    """
    This function validates the number of days for the weather forecast request.
    The number of days must be a string representation of an integer between 1 and 10 inclusive.

    Args:
        days (str): Number of days for the weather forecast.
    Returns:
        void
    """
    if not days.isdigit():
        raise ValueError(f"Days '{days}' must be a string representation of an integer")
    try:
        days_int = int(days)
        if not 1 <= days_int <= 10:
            raise ValueError(f"Days '{days}' must be an integer between 1 and 10 inclusive")
    except ValueError:
        raise ValueError(f"Days '{days}' must be a valid integer between 1 and 10 inclusive")
    

def get_forecast(location, days, aqi='no', alerts='no'):
    """
    This function retrieves weather forecast data from the Weather API for a specified location and number of days.
    The function can also include air quality and weather alerts data in the response.

    Args:
        location (str): Latitude and longitude coordinates of the location.
        days (str): Number of days for the weather forecast (between 1 and 10).
        aqi (str): Include air quality data in the response (yes or no).
        alerts (str): Include weather alerts data in the response (yes or no).
    Returns:
        dict: Raw weather forecast data from the Weather API.
    """
    validate_days(days)

    base_url = "http://api.weatherapi.com/v1/forecast.json"
    api_key = config.WEATHER_API_KEY
    url = f"{base_url}?key={api_key}&q={location}&days={days}&aqi={aqi}&alerts={alerts}"
    return send_api_request(url)


def process_weather_data(weather_data, day=None):
    """
    This function processes raw weather data from the Weather API and extracts the relevant information
    for further analysis. The function can return the data for a specific day or all days in the forecast.

    Args:
        weather_data (dict): Raw weather data from the Weather API.
        day (str): Optional parameter to specify a specific day in the forecast.
    Returns:
        dict: Processed weather data for the specified day or all days in the forecast.
    """

    results = []
    mins_per_hour = 60

    try:
        for daily_forecast in weather_data['forecast']['forecastday']:
            
            # Initialise total visible minutes for moon presence calculation
            total_visible_minutes = 0

            # Extract parent data
            astro = daily_forecast['astro']
            sunset = astro['sunset']
            moonrise = astro['moonrise']
            moonset = astro['moonset']
            moon_illumination = astro['moon_illumination']
            date = daily_forecast['date']

            # Parse moonrise and moonset into datetime objects
            moonrise_time = datetime.strptime(f"{date} {moonrise}", "%Y-%m-%d %I:%M %p")
            moonset_time = datetime.strptime(f"{date} {moonset}", "%Y-%m-%d %I:%M %p")

            # Handle case where moonsets after midnight by adding a day
            if moonset_time < moonrise_time:
                moonset_time += timedelta(days=1)

            # Round sunset time + 1h up to the nearest hour
            sunset_time = datetime.strptime(f"{date} {sunset}", "%Y-%m-%d %I:%M %p")
            rounded_time = (sunset_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            temp_time_str = rounded_time.strftime("%Y-%m-%d %H:%M")
            hour_data = {item['time']: item for item in daily_forecast['hour']}

            # Match each hour post-sunset to the corresponding data
            if temp_time_str in hour_data:
                selected_hour = hour_data[temp_time_str]

                # Extract data of interest
                temp_c = selected_hour['temp_c']
                dewpoint_c = selected_hour['dewpoint_c']
                wind_speed_kph = selected_hour['wind_kph']
                humidity = selected_hour['humidity']
                visibility_km = selected_hour['vis_km']

                # Determine average cloud cover and moon presence
                cloud_values = []
                for i in range(5):
                    hour = rounded_time + timedelta(hours=i)
                    hour_str = hour.strftime("%Y-%m-%d %H:%M")
                    if hour_str in hour_data:
                        cloud_values.append(hour_data[hour_str]['cloud'])
                        
                        # Calculate moon presence within the hour
                        moonrise_time = datetime.strptime(f"{date} {moonrise}", "%Y-%m-%d %I:%M %p")
                        moonset_time = datetime.strptime(f"{date} {moonset}", "%Y-%m-%d %I:%M %p")
                        if moonset_time < moonrise_time:  # Adjust for moonset after midnight
                            moonset_time += timedelta(days=1)
                        
                        # Check if moon is visible during this hour
                        if moonrise_time < hour + timedelta(hours=1) and moonset_time > hour:
                            visible_start = max(moonrise_time, hour)
                            visible_end = min(moonset_time, hour + timedelta(hours=1))
                            visible_minutes = (visible_end - visible_start).total_seconds() / 60
                            total_visible_minutes += visible_minutes

                # Calculate averages and percentages
                if cloud_values:
                    avg_cloud = sum(cloud_values) / len(cloud_values)
                    min_cloud = min(cloud_values)
                    max_cloud = max(cloud_values)
                else:
                    avg_cloud, min_cloud, max_cloud = None, None, None

                moon_presence_percent = (total_visible_minutes / (5 * mins_per_hour)) * 100

                # Construct output dictionary and append to results list
                results.append({
                    "date": date,
                    "sunset": sunset,
                    "moonrise": moonrise,
                    "moonset": moonset,
                    "moon_illumination": moon_illumination,
                    "temp_c": temp_c,
                    "dewpoint_c": dewpoint_c,
                    "wind_speed_kph": wind_speed_kph,
                    "humidity": humidity,
                    "visibility_km": visibility_km,
                    "avg_cloud": avg_cloud,
                    "min_cloud": min_cloud,
                    "max_cloud": max_cloud,
                    "moon_presence": moon_presence_percent
                })
                
    except KeyError as e:
        return {"error": f"Key error: Missing data {str(e)}"}

    if day is not None:
        validate_days(day)
        return results[int(day) - 1]

    return results


def calculate_suitability(processed_data):
    """
    This function models the suitability of astrophotography conditions based on the processed weather data.
    For example, we model the suitability of cloud cover (from 0-1) by passing the cloud% as an input to a logistic function.

    Args:
        processed_data (dict): Processed weather data for a specific day.
    Returns:
        dict: Modeled suitability scores for each condition.
    """

    def logistic_function(x, L=1, k=1, x0=0):
        """
        This function models a logistic function with parameters L, k, and x0.

        Args:
            x (float): Input value for the logistic function.
            L (float): Maximum value of the function.
            k (float): Logistic growth rate.
            x0 (float): Midpoint of the function.
        Returns:
            float: Output value of the logistic function.
        """

        output = L / (1 + pow(2.71828, -k * (x - x0)))
        if output > 100:
            return 100
        return output


    suitability = {
        "avg_cloud": logistic_function(
            processed_data['avg_cloud'], 
            config.SUITABILITY_PARAMS['cloud']['L'], 
            config.SUITABILITY_PARAMS['cloud']['k'], 
            config.SUITABILITY_PARAMS['cloud']['x0']
        ),
        "min_cloud": logistic_function(
            processed_data['min_cloud'], 
            config.SUITABILITY_PARAMS['cloud']['L'], 
            config.SUITABILITY_PARAMS['cloud']['k'], 
            config.SUITABILITY_PARAMS['cloud']['x0']
        ),
        "max_cloud": logistic_function(
            processed_data['max_cloud'], 
            config.SUITABILITY_PARAMS['cloud']['L'], 
            config.SUITABILITY_PARAMS['cloud']['k'], 
            config.SUITABILITY_PARAMS['cloud']['x0']
        )
    }

    return suitability