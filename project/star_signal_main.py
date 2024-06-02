import star_signal_utils as utils
import pushover_utils as notifs
import config
import json
import logging

# setup logging
logging.basicConfig(filename='forecast.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

def check_forecast():
    location = config.LOCATIONS['Adelaide']
    days = '7'
    
    forecast = utils.get_forecast(location, days)
    # utils.write_json_to_file(forecast, 'recent_forecast.json')
    # print(f'Sum of Weights: {sum(config.WEIGHTS.values())}')
    
    # with open('recent_forecast.json', 'r') as file:
    #     forecast = json.load(file)
    
    results = utils.process_weather_data(forecast)
    result_pretty = json.dumps(results, indent=4)
    # print(result_pretty)
    
    results_with_scores = utils.add_suitability_scores(results)
    results_with_scores_pretty = json.dumps(results_with_scores, indent=4)
    print(results_with_scores_pretty)
    
    suitabilities_json = utils.get_suitability_data(results)
    suitabilities_json_pretty = json.dumps(suitabilities_json, indent=4)
    # print(suitabilities_json_pretty)
    
    # suitabilities_json_pretty = json.dumps(suitabilities_json, indent=4)
    # print(suitabilities_json_pretty)
    
    utils.write_json_to_file(results_with_scores)
    
    days = 7
    total_score = results_with_scores[days - 1]['suitability_score']
    
    notification = utils.get_notification(results_with_scores)
    notification = utils.generate_summary_notification(results_with_scores, days)
    
    notifs.send_push_notification(config.USERS['Ethan'], notification, 'Ethan') if total_score >= 10.0 else None

import time
from datetime import datetime, timedelta

def task():
    try:
        logging.info("Running task...")
        check_forecast()
        logging.info("Task completed.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def main():
    task_done_today = False

    while True:
        current_time = datetime.now()
        run_time = current_time.replace(hour=11, minute=57, second=0, microsecond=0)

        if current_time >= run_time:
            if not task_done_today:
                task()
                task_done_today = True
        
        # reset flag after 10am following day
        if current_time >= run_time - timedelta(minutes=30) and task_done_today:
            task_done_today = False

        # sleep to avoid cpu use
        time.sleep(3)  # 5min


if __name__ == "__main__":
    main()
