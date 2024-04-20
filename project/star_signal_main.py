import star_signal_utils as utils
import config
import json

location = config.LOCATIONS['Adelaide']
days = '7'

forecast = utils.get_forecast(location, days)

# with open('example_forecast.json', 'r') as file:
#     forecast = json.load(file)

result = utils.process_weather_data(forecast, day=days)
result_pretty = json.dumps(result, indent=4)
print(result_pretty)