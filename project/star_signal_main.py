import star_signal_utils as utils
import config
import json

location = config.LOCATIONS['Adelaide']
days_from_today = '1'

# forecast = utils.get_forecast(location, days)
print(f'Sum of Weights: {sum(config.WEIGHTS.values())}')

with open('example_forecast.json', 'r') as file:
    forecast = json.load(file)

result = utils.process_weather_data(forecast, days_from_today=days_from_today)
result_pretty = json.dumps(result, indent=4)
print(result_pretty)

suitability = utils.calculate_suitability(result)
result_pretty = json.dumps(suitability, indent=4)
print(result_pretty)