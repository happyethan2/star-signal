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
    # print(results_with_scores_pretty)
    
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


def task():
    logging.info("Running task...")
    check_forecast()
    logging.info("Task completed.")

from datetime import datetime, timedelta
import time
import logging

TASK_HOUR = 10  # [24hr]
TASK_MINUTE = 0  # [min]
CHECK_INTERVAL = 600  # [sec]

def main():
    task_done_today = False
    last_reset_day = None

    while True:
        current_time = datetime.now()
        run_time = current_time.replace(hour=TASK_HOUR, minute=TASK_MINUTE, second=0, microsecond=0)

        print(f"Current time: {current_time}, Run time: {run_time}, Task done today: {task_done_today}")

        # if day crosses over to next
        if last_reset_day is not None and current_time.date() != last_reset_day:
            print("Day has changed, resetting task_done_today to False")
            task_done_today = False
            last_reset_day = current_time.date()

        # if current time past run time and task not done
        if current_time >= run_time and not task_done_today:
            try:
                print("Attempting to run task...")
                task()
                print("Task successfully run.")
                task_done_today = True
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                print("An error occurred while running the task.")
                pass

        # calculate sleep duration until next task or reset time
        if task_done_today:
            next_time = run_time + timedelta(days=1)
            sleep_duration = (next_time - current_time).total_seconds() - 60 # ensures earliest execution
        else:
            sleep_duration = CHECK_INTERVAL

        print(f"Sleeping for {sleep_duration/60/60:.2f} hours...")
        time.sleep(max(0, sleep_duration))  # sleep until next time, but never sleep a negative amount

if __name__ == "__main__":
    main()