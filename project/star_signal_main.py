import star_signal_utils as utils
import config
import json

location = config.LOCATIONS['Adelaide']
days_from_today = '7'

# forecast = utils.get_forecast(location, days)
print(f'Sum of Weights: {sum(config.WEIGHTS.values())}')

with open('example_forecast.json', 'r') as file:
    forecast = json.load(file)

result = utils.process_weather_data(forecast, days_from_today=days_from_today)
result_pretty = json.dumps(result, indent=4)
print(result_pretty)

suitability_data = utils.calculate_suitability_data(result)
result_pretty = json.dumps(suitability_data, indent=4)
print(result_pretty)

suitability_score = utils.getSuitability(suitability_data)
print(f'Suitability Score: {suitability_score:.2f}')