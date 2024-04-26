from __future__ import print_function
from datetime import datetime, timedelta

import requests
import json
import config
import swagger_client
import numpy as np


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


def process_weather_data(weather_data, days_from_today=None):
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

            # Extract parent elements
            astro = daily_forecast['astro']
            day = daily_forecast['day']

            sunset = astro['sunset']
            moonrise = astro['moonrise']
            moonset = astro['moonset']
            moon_illumination = astro['moon_illumination']
            mintemp_c = day['mintemp_c']
            date = daily_forecast['date']

            # Parse moonrise and moonset into datetime objects
            moonrise_time = datetime.strptime(f"{date} {moonrise}", "%Y-%m-%d %I:%M %p")
            moonset_time = datetime.strptime(f"{date} {moonset}", "%Y-%m-%d %I:%M %p")
            sunset_time = datetime.strptime(f"{date} {sunset}", "%Y-%m-%d %I:%M %p")

            # Handle case where moonsets after midnight by adding a day
            # E: moonset = 00:30, moonrise = 18:00
            if moonset_time < moonrise_time:
                moonset_time += timedelta(days=1)


            # Round sunset time + 1h up to the nearest hour
            rounded_time = (sunset_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            temp_time_str = rounded_time.strftime("%Y-%m-%d %H:%M")
            hour_data = {item['time']: item for item in daily_forecast['hour']}

            # Match each hour post-sunset to the corresponding data
            if temp_time_str in hour_data:
                selected_hour = hour_data[temp_time_str]

                # Extract data of interest
                temp_c = selected_hour['temp_c']
                dewpoint_risk = selected_hour['dewpoint_c'] - mintemp_c
                wind_speed_kph = selected_hour['wind_kph']
                humidity = selected_hour['humidity']
                visibility_km = selected_hour['vis_km']

                # Determine average cloud cover and moon presence
                cloud_values = []
                dewpoint_values = []
                for i in range(5):
                    hour = rounded_time + timedelta(hours=i)
                    hour_str = hour.strftime("%Y-%m-%d %H:%M")
                    if hour_str in hour_data:
                        cloud_values.append(hour_data[hour_str]['cloud'])
                        dewpoint_values.append(hour_data[hour_str]['dewpoint_c'])
                        
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
                
                if dewpoint_values:
                    avg_dewpoint = sum(dewpoint_values) / len(dewpoint_values)
                    min_dewpoint = min(dewpoint_values)

                moon_presence_percent = (total_visible_minutes / (5 * mins_per_hour)) * 100

                # Construct output dictionary and append to results list
                results.append({
                    "date": date,
                    "sunset": sunset,
                    "moonrise": moonrise,
                    "moonset": moonset,
                    "moon_illumination": moon_illumination,
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
                    "moon_presence": moon_presence_percent
                })
                
    except KeyError as e:
        return {"error": f"Key error: Missing data {str(e)}"}

    if days_from_today is not None:
        validate_days(days_from_today)
        return results[int(days_from_today) - 1]

    return results


def calculate_suitability_data(processed_data):
    """
    This function models the suitability of astrophotography conditions based on the processed weather data.
    For example, we model the suitability of cloud cover (from 0-1) by passing the cloud% as an input to a logistic function.

    Args:
        processed_data (dict): Processed weather data for a specific day.
    Returns:
        dict: Modeled suitability scores for each condition.
    """

    def log_function(x, A, B, k, x0, condition=None):
        """
        This function models a logarithmic function with parameters A, B, k, and x0.

        Args:
            x (float): Input value for the logarithmic function.
            A (float): Scaling factor.
            B (float): Vertical shift.
            k (float): Growth rate.
            x0 (float): Midpoint of the function.
            condition (int): The condition being modelled.
                1: visibility (km),
        """

        # Ensure we don't pass a non-positive value to the logarithm
        inside_log = k * (x - x0)
        if inside_log <= 0:
            raise ValueError("k * (x1 - x0) must be positive to evaluate the natural log.")
        
        output = A * np.log(inside_log) + B
        return output

    def logistic_function(x, L, k, x0, condition=None):
        """
        This function models a logistic function with parameters L, k, and x0.
        The output is arbitrarily capped at 100 due to imperfect parameter estimation.

        Args:
            x (float): Input value for the logistic function.
            L (float): Maximum value of the function.
            k (float): Logistic growth rate.
            x0 (float): Midpoint of the function.
            condition (int): The condition being modelled.
                1: cloud (%),
                2: moon,
                3: moon_presence,
                4: moon_illumination,
        Returns:
            float: Output value of the logistic function.
        """

        # Validate condition
        if condition not in [1, 2, 3, 4, 5] and condition is not None:
            raise ValueError("Invalid condition: Must be 1 (cloud) or 2 (moon)")
        
        # Evaluate function
        output = L / (1 + pow(2.71828, -k * (x - x0)))

        # Maximum output value = 100
        if output > 100:
                return 100

        # Cloud: 30% or more is unsuitable
        if condition == 1:
            if x >= 30:
                return 0
        # Moon Presence: 50% or more is unsuitable
        if condition == 2:
            if x >= 50:
                return 0
        # Moon Illumination: 40% or more is unsuitable
        if condition == 3:
            if x >= 40:
                return 0
        # Wind Speed: 40 km/h or more is unsuitable
        if condition == 4:
            if x >= 40:
                return 0
        # Dewpoint Risk: 6 degrees or more is unsuitable
        if condition == 5:
            if x >= 6:
                return 0

        return output
    

    avg_cloud_suitability = logistic_function(
        processed_data['avg_cloud'],
        config.SUITABILITY_PARAMS['cloud']['L'],
        config.SUITABILITY_PARAMS['cloud']['k'],
        config.SUITABILITY_PARAMS['cloud']['x0'], 1
    )
    min_cloud_suitability = logistic_function(
        processed_data['min_cloud'],
        config.SUITABILITY_PARAMS['cloud']['L'],
        config.SUITABILITY_PARAMS['cloud']['k'],
        config.SUITABILITY_PARAMS['cloud']['x0'], 1
    )
    max_cloud_suitability = logistic_function(
        processed_data['max_cloud'],
        config.SUITABILITY_PARAMS['cloud']['L'],
        config.SUITABILITY_PARAMS['cloud']['k'],
        config.SUITABILITY_PARAMS['cloud']['x0'], 1
    )
    moon_presence_suitability = logistic_function(
        processed_data['moon_presence'],
        config.SUITABILITY_PARAMS['moon_presence']['L'],
        config.SUITABILITY_PARAMS['moon_presence']['k'],
        config.SUITABILITY_PARAMS['moon_presence']['x0'], 2
    )
    moon_illumination_suitability = logistic_function(
        processed_data['moon_illumination'],
        config.SUITABILITY_PARAMS['moon_presence']['L'],
        config.SUITABILITY_PARAMS['moon_presence']['k'],
        config.SUITABILITY_PARAMS['moon_presence']['x0'], 3
    )
    wind_speed_suitability = logistic_function(
        processed_data['wind_speed_kph'],
        config.SUITABILITY_PARAMS['wind_speed']['L'],
        config.SUITABILITY_PARAMS['wind_speed']['k'],
        config.SUITABILITY_PARAMS['wind_speed']['x0'], 4
    )
    humidity_suitability = logistic_function(
        processed_data['humidity'],
        config.SUITABILITY_PARAMS['humidity']['L'],
        config.SUITABILITY_PARAMS['humidity']['k'],
        config.SUITABILITY_PARAMS['humidity']['x0']
    )
    visibility_suitability = log_function(
        processed_data['visibility_km'],
        config.SUITABILITY_PARAMS['visibility']['A'],
        config.SUITABILITY_PARAMS['visibility']['B'],
        config.SUITABILITY_PARAMS['visibility']['k'],
        config.SUITABILITY_PARAMS['visibility']['x0']
    )
    dewpoint_risk_suitability = logistic_function(
        processed_data['dewpoint_risk'],
        config.SUITABILITY_PARAMS['dewpoint_risk']['L'],
        config.SUITABILITY_PARAMS['dewpoint_risk']['k'],
        config.SUITABILITY_PARAMS['dewpoint_risk']['x0'], 5
    )

    suitability = {
        "date": processed_data['date'],
        "avg_cloud": avg_cloud_suitability,
        "min_cloud": min_cloud_suitability,
        "max_cloud": max_cloud_suitability,
        "moon_presence": moon_presence_suitability,
        "moon_illumination": moon_illumination_suitability,
        "wind_speed": wind_speed_suitability,
        "humidity": humidity_suitability,
        "visibility": visibility_suitability,
        "dewpoint_risk": dewpoint_risk_suitability
    }

    return suitability


def get_suitability(suitability_data):
    """
    This function calculates the overall suitability score based on the individual suitability scores for each condition.
    The overall suitability score is the weighted sum of the individual suitability scores.

    Args:
        suitability_data (dict): Individual suitability scores for each condition.
    Returns:
        float: Overall suitability score.
    """
    
    weights = config.WEIGHTS
    suitability_score = sum([suitability_data[condition] * weights[condition] 
                             for condition in suitability_data if condition in weights])
    return suitability_score


def get_suitability_data(calculated_data):
    """
    This function calculates the suitability scores for a list of calculated data.

    Args:
        calculated_data (list): Processed weather data for each day.
    Returns:
        list: Suitability scores for each day.
    """
    suitability_data = [calculate_suitability_data(day) for day in calculated_data]

    for day in suitability_data:
        day['suitability_score'] = get_suitability(day)

    return suitability_data


def add_suitability_scores(processed_data):
    """
    This function adds the overall suitability scores to the processed weather data.

    Args:
        processed_data (list): Processed weather data for a list of days.
    Returns:
        list: Processed data with overall suitability scores for each day.
    """

    for day in processed_data:
        suitability_data = calculate_suitability_data(day)
        day['suitability_score'] = get_suitability(suitability_data)
    return processed_data


def write_json_to_file(data, filepath=None):
    """
    This function writes a list of JSON objects to a file.

    Args:
        data (list): A list of JSON objects.
        filepath (str, optional): The path of the file to write to. If not provided, the function will construct a filename using the start and end dates from the data.
    """
    if filepath is None:
        start_date = datetime.strptime(data[0]['date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data[-1]['date'], '%Y-%m-%d').date()
        filepath = f'output_data/results_{start_date}_to_{end_date}.json'

    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)