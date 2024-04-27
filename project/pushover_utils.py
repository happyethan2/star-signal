import requests
import config

def send_push_notification(user_key, message, user_name='user'):
    try:
        url = "https://api.pushover.net/1/messages.json"
        payload = {
            "token": config.PUSHOVER_APP_TOKEN,
            "user": user_key,
            "message": message,
            "title": "Star Signal Alert"
        }
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Error sending notification to {user_name}: {response.text}")
    except Exception as e:
        print(f"Error sending notification to {user_name}: {e}")