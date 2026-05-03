"""
Script สำหรับตั้งค่า Telegram Webhook
รันครั้งเดียวหลัง deploy แล้ว:
    python setup_webhook.py
"""
import requests
from app.config import settings


def set_webhook():
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": f"{settings.TELEGRAM_WEBHOOK_URL}",
        "allowed_updates": ["message"],
    }
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")


def get_webhook_info():
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url)
    print(f"Webhook Info: {response.json()}")


if __name__ == "__main__":
    print("Setting up Telegram webhook...")
    set_webhook()
    print("\nWebhook info:")
    get_webhook_info()
