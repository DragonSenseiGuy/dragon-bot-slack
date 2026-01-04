import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY")
URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
USAGE_FILE = Path(__file__).parent.parent / "resources" / "ai_usage.json"
DAILY_LIMIT = 20

PERSONALITY = [
    "discord zoomer",
    "potter head",
    "roasting mode",
    "'You are absolutely right' mode",
]


def check_and_increment_usage() -> bool:
    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"date": "", "count": 0}

    today = datetime.now().strftime("%Y-%m-%d")

    if data["date"] != today:
        data["date"] = today
        data["count"] = 1
    elif data["count"] >= DAILY_LIMIT:
        return False
    else:
        data["count"] += 1

    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logging.error(f"Failed to write to usage file: {e}")

    return True


def register(app):
    @app.command("/generate-image")
    def generate_image(ack, command):
        ack()

        if not AI_API_KEY:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage():
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/generate-image <prompt>`",
            )
            return

        app.client.chat_postMessage(
            channel=command["channel_id"],
            text="Generating image... please wait.",
        )

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash-image",
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": "16:9"},
        }

        try:
            response = requests.post(URL, headers=headers, json=payload)
            result = response.json()

            if result.get("choices"):
                message = result["choices"][0]["message"]
                if message.get("images"):
                    image_url = message["images"][0]["image_url"]["url"]
                    if "," in image_url:
                        base64_data = image_url.split(",")[1]
                    else:
                        base64_data = image_url

                    image_bytes = base64.b64decode(base64_data)

                    app.client.files_upload_v2(
                        channel=command["channel_id"],
                        file=image_bytes,
                        filename="generated_image.png",
                        initial_comment=f"Generated image for: {prompt}",
                    )
                    return

            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="I couldn't generate an image. The API returned no image.",
            )
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to generate image: {e}",
            )

    @app.command("/ask-ai")
    def ask_ai(ack, command):
        ack()

        if not AI_API_KEY:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage():
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai <prompt>`",
            )
            return

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        try:
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = result["choices"][0]["message"]["content"]
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text="I couldn't get a response from the AI.",
                )
        except Exception as e:
            logging.error(f"Error asking AI: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to communicate with the AI API: {e}",
            )

    @app.command("/ask-ai-personality")
    def ask_ai_with_personality(ack, command):
        ack()

        if not AI_API_KEY:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage():
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai-personality <prompt>`",
            )
            return

        import random

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {"role": "system", "content": f"Act like a {random.choice(PERSONALITY)}"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        try:
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = result["choices"][0]["message"]["content"]
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text="I couldn't get a response from the AI.",
                )
        except Exception as e:
            logging.error(f"Error asking AI: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to communicate with the AI API: {e}",
            )
