import base64
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
USAGE_FILE = Path(__file__).parent.parent / "resources" / "ai_usage.json"
DAILY_LIMIT = 20

CHAT_CHANNEL = "C0AE6U84NJC"

CHAT_SYSTEM_PROMPT = (
    "You are Dragon Bot, a helpful and friendly Slack bot for the Hack Club community. "
    "Keep your responses concise and conversational. "
    "Use the web_search tool if you need current information or facts you're unsure about. "
    "Format your responses using Slack mrkdwn syntax."
)

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information when you need up-to-date facts or answers you're unsure about.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    },
}


def do_web_search(query):
    """Search using Hack Club Search API."""
    headers = {"Authorization": f"Bearer {SEARCH_API_KEY}"}
    resp = requests.get(
        "https://search.hackclub.com/res/v1/web/search",
        params={"q": query, "count": 5},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("web", {}).get("results", [])
    formatted = []
    for r in results:
        formatted.append(
            f"Title: {r.get('title', '')}\n"
            f"URL: {r.get('url', '')}\n"
            f"Snippet: {r.get('description', '')}"
        )
    return "\n\n".join(formatted) if formatted else "No results found."

PERSONALITY = [
    "discord zoomer",
    "potter head",
    "roasting mode",
    "'You are absolutely right' mode",
]


def check_and_increment_usage() -> bool:
    logging.debug("Checking AI usage limit...")
    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
        logging.debug(f"Loaded usage data: {data}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Could not load usage file, creating new: {e}")
        data = {"date": "", "count": 0}

    today = datetime.now().strftime("%Y-%m-%d")

    if data["date"] != today:
        logging.info(f"New day detected, resetting usage count")
        data["date"] = today
        data["count"] = 1
    elif data["count"] >= DAILY_LIMIT:
        logging.warning(f"Daily limit reached: {data['count']}/{DAILY_LIMIT}")
        return False
    else:
        data["count"] += 1
        logging.debug(f"Usage count incremented: {data['count']}/{DAILY_LIMIT}")

    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        logging.debug("Usage data saved successfully")
    except Exception as e:
        logging.error(f"Failed to write to usage file: {e}")

    return True


def register(app):
    @app.command("/generate-image")
    def generate_image(ack, command):
        ack()
        logging.info(f"/generate-image used by <@{command['user_id']}>")

        if not AI_API_KEY:
            logging.error("AI API key not configured")
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
            logging.debug("No prompt provided for /generate-image")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/generate-image <prompt>`",
            )
            return

        logging.info(f"Generating image with prompt: {prompt[:50]}...")
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
            logging.debug(f"Sending image generation request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices"):
                message = result["choices"][0]["message"]
                if message.get("images"):
                    logging.info("Image generated successfully, uploading to Slack")
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
                    logging.info("Image uploaded to Slack successfully")
                    return

            logging.warning("API returned no image in response")
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
        logging.info(f"/ask-ai used by <@{command['user_id']}>")

        if not AI_API_KEY:
            logging.error("AI API key not configured")
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
            logging.debug("No prompt provided for /ask-ai")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai <prompt>`",
            )
            return

        logging.info(f"Asking AI with prompt: {prompt[:50]}...")
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
            logging.debug(f"Sending AI request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = result["choices"][0]["message"]["content"]
                logging.info(f"AI response received, length: {len(content)} chars")
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                logging.warning("AI returned empty response")
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

    @app.event("app_mention")
    def handle_mention(event, say):
        channel = event.get("channel")
        if channel != CHAT_CHANNEL:
            return

        user_id = event.get("user")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        user_message = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not user_message:
            say(text="Hey! What can I help you with?", thread_ts=thread_ts)
            return

        if not AI_API_KEY:
            say(text=":x: The AI API key is not configured.", thread_ts=thread_ts)
            return

        if not check_and_increment_usage():
            say(
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
                thread_ts=thread_ts,
            )
            return

        logging.info(f"AI mention from <@{user_id}>: {user_message[:50]}...")

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": "moonshotai/kimi-k2.5",
            "messages": messages,
            "stream": False,
        }
        if SEARCH_API_KEY:
            payload["tools"] = [SEARCH_TOOL]

        try:
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})

            if message.get("tool_calls"):
                tool_call = message["tool_calls"][0]
                if tool_call["function"]["name"] == "web_search":
                    args = json.loads(tool_call["function"]["arguments"])
                    search_query = args.get("query", user_message)
                    logging.info(f"AI requested web search: {search_query}")

                    search_results = do_web_search(search_query)

                    messages.append(message)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": search_results,
                        }
                    )

                    payload["messages"] = messages
                    payload.pop("tools", None)

                    response = requests.post(URL, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    choice = result.get("choices", [{}])[0]
                    message = choice.get("message", {})

            content = message.get("content", "")
            if content:
                logging.info(f"AI chat response sent, length: {len(content)} chars")
                say(text=content, thread_ts=thread_ts)
            else:
                say(text="I couldn't come up with a response.", thread_ts=thread_ts)
        except Exception as e:
            logging.error(f"Error in AI chat mention: {e}")
            say(text=f":x: Something went wrong: {e}", thread_ts=thread_ts)

    @app.command("/ask-ai-personality")
    def ask_ai_with_personality(ack, command):
        ack()
        logging.info(f"/ask-ai-personality used by <@{command['user_id']}>")

        if not AI_API_KEY:
            logging.error("AI API key not configured")
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
            logging.debug("No prompt provided for /ask-ai-personality")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai-personality <prompt>`",
            )
            return

        import random

        selected_personality = random.choice(PERSONALITY)
        logging.info(f"Using personality: {selected_personality}")
        logging.info(f"Asking AI with prompt: {prompt[:50]}...")

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {"role": "system", "content": f"Act like a {selected_personality}"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        try:
            logging.debug(f"Sending AI request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = result["choices"][0]["message"]["content"]
                logging.info(f"AI response received, length: {len(content)} chars")
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                logging.warning("AI returned empty response")
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
