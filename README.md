# Star Signal

## Description
Star Signal is a project designed to alert astrophotography enthusiasts about the optimal nights for capturing the stars. Utilizing real-time weather forecasts, moon phases, and atmospheric conditions, the model calculates a suitability score for astrophotography. Alerts are sent to your phone if the total suitability for a night exceeds 50%, ensuring you never miss an ideal skygazing opportunity.

## Features
- **Real-time Weather and Moon Phase Data**: Leverages weather forecasts and moon phase data to assess conditions.
- **Logistic Modeling**: Uses logistic maps to convert meteorological and astronomical data into a suitability score.
- **Push Notifications**: Sends tailored alerts via Pushover when conditions are favorable.

## Components
The project consists of several Python scripts:
- `star_signal_utils.py`: Contains utility functions for fetching weather data, processing it, and calculating suitability scores.
- `star_signal_main.py`: Main script that orchestrates data fetching, processing, and alerting.
- `pushover_utils.py`: Handles the sending of push notifications to users.

## Dependencies
- Python 3.x
- Libraries: `requests`, `json`, `numpy`, `config`, `swagger_client`
- External APIs:
  - Weather API (WeatherAPI.com)
  - Moon Phase API (RapidAPI)
  - Pushover for notifications

## Setup
1. Install required Python packages:

   `pip install requests numpy swagger-client`

2. Configure `config.py` with necessary API keys and user settings:
   - Weather API key
   - Moon Phase API key
   - Pushover application token and user keys

## Usage
Run `star_signal_main.py` to start the process:
   python star_signal_main.py
This script will automatically fetch weather data, calculate the suitability score, and send notifications if the conditions are favorable.

## Notifications
Notifications are sent only when the suitability score for a night is above 50%. They include detailed information such as cloud coverage, moon presence, and overall potential, helping you plan your astrophotography sessions effectively.

## Contributing
Contributions to the project are welcome. Please fork the repository, make your changes, and submit a pull request.
