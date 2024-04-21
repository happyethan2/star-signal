import star_signal_utils as utils
import config
import json

location = config.LOCATIONS['Adelaide']
day_of_forecast = '1'

# forecast = utils.get_forecast(location, days)
print(f'Sum of Weights: {sum(config.WEIGHTS.values())}')

with open('example_forecast.json', 'r') as file:
    forecast = json.load(file)

result = utils.process_weather_data(forecast, day=day_of_forecast)
result_pretty = json.dumps(result, indent=4)
print(result_pretty)

suitability = utils.calculate_suitability(result)
result_pretty = json.dumps(suitability, indent=4)
print(result_pretty)