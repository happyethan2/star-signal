import star_signal_utils as utils
import config
import json

location = config.LOCATIONS['Adelaide']
days = '7'

# forecast = utils.get_forecast(location, days)
print(f'Sum of Weights: {sum(config.WEIGHTS.values())}')

with open('example_forecast.json', 'r') as file:
    forecast = json.load(file)

results = utils.process_weather_data(forecast)
result_pretty = json.dumps(results, indent=4)
# print(result_pretty)

suitabilities_json = utils.get_suitability_data(results)
suitabilities_json_pretty = json.dumps(suitabilities_json, indent=4)
print(suitabilities_json_pretty)

# suitabilities_json_pretty = json.dumps(suitabilities_json, indent=4)
# print(suitabilities_json_pretty)