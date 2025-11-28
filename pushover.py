import os

import requests
from loguru import logger

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def send_pushover_alert(title: str, message: str):
    """Sends an alert via Pushover"""
    user_key = os.getenv("PUSHOVER_USER_KEY")
    api_token = os.getenv("PUSHOVER_API_TOKEN")

    if not user_key or not api_token:
        logger.error("Pushover credentials not configured.")
        return

    payload = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "title": title,
        "priority": 1,  # -2 to 2; 1 is High Priority
    }
    try:
        response = requests.post(PUSHOVER_URL, data=payload)
        response.raise_for_status()
        logger.info(f"Pushover alert sent successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Pushover alert: {e}")
        if response is not None:
            print(f"Pushover response: {response.text}")
