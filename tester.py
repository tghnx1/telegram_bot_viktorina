from locust import HttpUser, task, between
import random
import json

BOT_TOKEN = "5111196744:AAHk1ecAM9XcI3ShPilY0OUSOqCHfFFreNA"
CHAT_ID = "-4805839645"  # Use your real chat ID

class TelegramBotUser(HttpUser):
    wait_time = between(2, 3)

    @task
    def send_message(self):
        message_text = f"Test message оливье {random.randint(1, 1000)}"
        payload = {
            "chat_id": CHAT_ID,
            "text": message_text
        }
        headers = {
            "Content-Type": "application/json"
        }
        self.client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=json.dumps(payload),
            headers=headers,
        )
